# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

# python genTFRecord.py --craigcap_image_dir=craigcapImg

# to call:
#
# python genTFRecord.py \
# --craigcap_image_dir=craigcapImg \
# --craigcap_captions_dir=craigcapAnno \
# --output_dir=out \
# --word_counts_output_file=out/word_counts.txt \
"""Converts craigcap data to TFRecord file format with SequenceExample protos.

The craigcap images are expected to reside in JPEG files located in the following
directory structure:

  craigcapImg/erie/00000_3GL6XnTmyaG.jpg
  craigcapImg/sfbay/00000_4XL6XnTmyaQ.jpg
  ...


The craigcap annotations CSV files are expected to reside in craigcapAnno directory

This script converts the craigcapImg data into sharded data files consisting
of 256, 8 and 8 TFRecord files, respectively:

  out/train-00000-of-00256
  out/train-00001-of-00256
  ...
  out/train-00255-of-00256

and

  out/val-00000-of-00008
  ...
  out/val-00003-of-00008

and

  out/test-00000-of-00008
  ...
  out/test-00007-of-00008

Each TFRecord file contains ~(TODO) records. Each record within the TFRecord file
is a serialized SequenceExample proto consisting of precisely one image-caption
pair. Note that each image has could have multiple and therefore an
image could replicated multiple times in the TFRecord files.

The SequenceExample proto contains the following fields:

  context:
    image/image_id: string craigcap image identifier taken from filename
    image/data: string containing JPEG encoded image in RGB colorspace

  feature_lists:
    image/caption: list of strings containing the (tokenized) caption words
    image/caption_ids: list of integer ids corresponding to the caption words

The captions are tokenized using the NLTK (http://www.nltk.org/) word tokenizer.
The vocabulary of word identifiers is constructed from the sorted list (by
descending frequency) of word tokens in the training set. Only tokens appearing
at least 4 times are considered; all other words get the "unknown" word id.

NOTE: This script will consume around (TODO)GB of disk space.

Running this script using 16 threads may take around (TODO) hour on a mid level 2014 pc.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from collections import Counter
from collections import namedtuple
from datetime import datetime
import json
import csv
import os.path
import random
import sys
import threading



import nltk.tokenize
import numpy as np
import tensorflow as tf

tf.flags.DEFINE_string("craigcap_image_dir", "craigcapImg",
                       "Training image directory.")

tf.flags.DEFINE_string("craigcap_captions_dir", "craigcapAnno",
                       "Training captions JSON file.")

tf.flags.DEFINE_string("output_dir", "out", "Output data directory.")

tf.flags.DEFINE_integer("train_shards", 256,
                        "Number of shards in training TFRecord files.")
tf.flags.DEFINE_integer("val_shards", 8,
                        "Number of shards in validation TFRecord files.")
tf.flags.DEFINE_integer("test_shards", 8,
                        "Number of shards in testing TFRecord files.")

tf.flags.DEFINE_string("start_word", "<S>",
                       "Special word added to the beginning of each sentence.")
tf.flags.DEFINE_string("end_word", "</S>",
                       "Special word added to the end of each sentence.")
tf.flags.DEFINE_string("unknown_word", "<UNK>",
                       "Special word meaning 'unknown'.")
tf.flags.DEFINE_integer("min_word_count", 4,
                        "The minimum number of occurrences of each word in the "
                        "training set for inclusion in the vocabulary.")
tf.flags.DEFINE_string("word_counts_output_file", "out/word_counts.txt",
                       "Output vocabulary file of word counts.")

tf.flags.DEFINE_integer("num_threads", 8,
                        "Number of threads to preprocess the images.")

FLAGS = tf.flags.FLAGS

ImageMetadata = namedtuple("ImageMetadata",
                           ["image_id", "filename", "captions"])


class Vocabulary(object):
  """Simple vocabulary wrapper."""

  def __init__(self, vocab, unk_id):
    """Initializes the vocabulary.

    Args:
      vocab: A dictionary of word to word_id.
      unk_id: Id of the special 'unknown' word.
    """
    self._vocab = vocab
    self._unk_id = unk_id

  def word_to_id(self, word):
    """Returns the integer id of a word string."""
    if word in self._vocab:
      return self._vocab[word]
    else:
      return self._unk_id


class ImageDecoder(object):
  """Helper class for decoding images in TensorFlow."""

  def __init__(self):
    # Create a single TensorFlow Session for all image decoding calls.
    self._sess = tf.Session()

    # TensorFlow ops for JPEG decoding.
    self._encoded_jpeg = tf.placeholder(dtype=tf.string)
    self._decode_jpeg = tf.image.decode_jpeg(self._encoded_jpeg, channels=3)

  def decode_jpeg(self, encoded_jpeg):
    image = self._sess.run(self._decode_jpeg,
                           feed_dict={self._encoded_jpeg: encoded_jpeg})
    assert len(image.shape) == 3
    assert image.shape[2] == 3
    return image


def _int64_feature(value):
  """Wrapper for inserting an int64 Feature into a SequenceExample proto."""
  return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))


def _bytes_feature(value):
  """Wrapper for inserting a bytes Feature into a SequenceExample proto."""
  return tf.train.Feature(bytes_list=tf.train.BytesList(value=[str(value)]))


def _int64_feature_list(values):
  """Wrapper for inserting an int64 FeatureList into a SequenceExample proto."""
  return tf.train.FeatureList(feature=[_int64_feature(v) for v in values])


def _bytes_feature_list(values):
  """Wrapper for inserting a bytes FeatureList into a SequenceExample proto."""
  return tf.train.FeatureList(feature=[_bytes_feature(v) for v in values])


def _to_sequence_example(image, decoder, vocab):
  """Builds a SequenceExample proto for an image-caption pair.

  Args:
    image: An ImageMetadata object.
    decoder: An ImageDecoder object.
    vocab: A Vocabulary object.

  Returns:
    A SequenceExample proto.
  """
  with tf.gfile.FastGFile(image.filename, "r") as f:
    try:
      encoded_image = f.read()
      decoder.decode_jpeg(encoded_image)
      context = tf.train.Features(feature={
          "image/image_id": _bytes_feature(image.image_id), # we are using the filename string as the identifier instead of an int
          "image/data": _bytes_feature(encoded_image),
      })
      assert len(image.captions) == 1
      caption = image.captions[0]
      caption_ids = [vocab.word_to_id(word) for word in caption]
      feature_lists = tf.train.FeatureLists(feature_list={
          "image/caption": _bytes_feature_list(caption),
          "image/caption_ids": _int64_feature_list(caption_ids)
      })
      sequence_example = tf.train.SequenceExample(
          context=context, feature_lists=feature_lists)
      return sequence_example
    except (tf.errors.InvalidArgumentError, AssertionError):
      print("Skipping file with invalid JPEG data: %s" % image.filename)
      return
    except UnicodeDecodeError:
      print("Skipping file because unicode decode error %s" % (image.filename))
      return


def _process_image_files(thread_index, ranges, name, images, decoder, vocab,
                         num_shards):
  """Processes and saves a subset of images as TFRecord files in one thread.

  Args:
    thread_index: Integer thread identifier within [0, len(ranges)].
    ranges: A list of pairs of integers specifying the ranges of the dataset to
      process in parallel.
    name: Unique identifier specifying the dataset.
    images: List of ImageMetadata.
    decoder: An ImageDecoder object.
    vocab: A Vocabulary object.
    num_shards: Integer number of shards for the output files.
  """
  # Each thread produces N shards where N = num_shards / num_threads. For
  # instance, if num_shards = 128, and num_threads = 2, then the first thread
  # would produce shards [0, 64).
  num_threads = len(ranges)
  assert not num_shards % num_threads
  num_shards_per_batch = int(num_shards / num_threads)

  shard_ranges = np.linspace(ranges[thread_index][0], ranges[thread_index][1],
                             num_shards_per_batch + 1).astype(int)
  num_images_in_thread = ranges[thread_index][1] - ranges[thread_index][0]

  counter = 0

  # Changed xrange to range because we are running python3 not python2
  for s in range(num_shards_per_batch):
    # Generate a sharded version of the file name, e.g. 'train-00002-of-00010'
    shard = thread_index * num_shards_per_batch + s
    output_filename = "%s-%.5d-of-%.5d" % (name, shard, num_shards)
    output_file = os.path.join(FLAGS.output_dir, output_filename)
    writer = tf.python_io.TFRecordWriter(output_file)

    shard_counter = 0
    images_in_shard = np.arange(shard_ranges[s], shard_ranges[s + 1], dtype=int)
    for i in images_in_shard:
      image = images[i]

      sequence_example = _to_sequence_example(image, decoder, vocab)
      if sequence_example is not None:
        writer.write(sequence_example.SerializeToString())
        shard_counter += 1
        counter += 1

      if not counter % 1000:
        print("%s [thread %d]: Processed %d of %d items in thread batch." %
              (datetime.now(), thread_index, counter, num_images_in_thread))
        sys.stdout.flush()

    writer.close()
    print("%s [thread %d]: Wrote %d image-caption pairs to %s" %
          (datetime.now(), thread_index, shard_counter, output_file))
    sys.stdout.flush()
    shard_counter = 0
  print("%s [thread %d]: Wrote %d image-caption pairs to %d shards." %
        (datetime.now(), thread_index, counter, num_shards_per_batch))
  sys.stdout.flush()


def _process_dataset(name, images, vocab, num_shards):
  """Processes a complete data set and saves it as a TFRecord.

  Args:
    name: Unique identifier specifying the dataset.
    images: List of ImageMetadata.
    vocab: A Vocabulary object.
    num_shards: Integer number of shards for the output files.
  """
  # Break up each image into a separate entity for each caption.
  images = [ImageMetadata(image.image_id, image.filename, [caption])
            for image in images for caption in image.captions]

  # Shuffle the ordering of images. Make the randomization repeatable.
  random.seed(12345)
  random.shuffle(images)

  # Break the images into num_threads batches. Batch i is defined as
  # images[ranges[i][0]:ranges[i][1]].
  num_threads = min(num_shards, FLAGS.num_threads)
  spacing = np.linspace(0, len(images), num_threads + 1).astype(np.int)
  ranges = []
  threads = []

  # Changed xrange to range because we are running python3 not python2
  for i in range(len(spacing) - 1):
    ranges.append([spacing[i], spacing[i + 1]])

  # Create a mechanism for monitoring when all threads are finished.
  coord = tf.train.Coordinator()

  # Create a utility for decoding JPEG images to run sanity checks.
  decoder = ImageDecoder()

  # Launch a thread for each batch.
  print("Launching %d threads for spacings: %s" % (num_threads, ranges))
  
  # Changed xrange to range because we are running python3 not python2
  for thread_index in range(len(ranges)):
    args = (thread_index, ranges, name, images, decoder, vocab, num_shards)
    t = threading.Thread(target=_process_image_files, args=args)
    t.start()
    threads.append(t)

  # Wait for all the threads to terminate.
  coord.join(threads)
  print("%s: Finished processing all %d image-caption pairs in data set '%s'." %
        (datetime.now(), len(images), name))


def _create_vocab(captions):
  """Creates the vocabulary of word to word_id.

  The vocabulary is saved to disk in a text file of word counts. The id of each
  word in the file is its corresponding 0-based line number.

  Args:
    captions: A list of lists of strings.

  Returns:
    A Vocabulary object.
  """
  print("Creating vocabulary.")
  counter = Counter()
  for c in captions:
    counter.update(c)
  print("Total words:", len(counter))

  # Filter uncommon words and sort by descending count.
  word_counts = [x for x in counter.items() if x[1] >= FLAGS.min_word_count]
  word_counts.sort(key=lambda x: x[1], reverse=True)
  print("Words in vocabulary:", len(word_counts))

  # Write out the word counts file.
  with tf.gfile.FastGFile(FLAGS.word_counts_output_file, "w") as f:
    f.write("\n".join(["%s %d" % (w, c) for w, c in word_counts]))
  print("Wrote vocabulary file:", FLAGS.word_counts_output_file)

  # Create the vocabulary dictionary.
  reverse_vocab = [x[0] for x in word_counts]
  unk_id = len(reverse_vocab)
  vocab_dict = dict([(x, y) for (y, x) in enumerate(reverse_vocab)])
  vocab = Vocabulary(vocab_dict, unk_id)

  return vocab


def _process_caption(caption):
  """Processes a caption string into a list of tonenized words.

  Args:
    caption: A string caption.

  Returns:
    A list of strings; the tokenized caption.
  """
  tokenized_caption = [FLAGS.start_word]
  tokenized_caption.extend(nltk.tokenize.word_tokenize(caption.lower()))
  tokenized_caption.append(FLAGS.end_word)
  return tokenized_caption


def show(n, xs, desc):
  print("\n\tprinting first "+str(len(xs[0:n]))+" items of "+str(len(xs))+" for "+desc+"\n" )
  for x in xs[0:n]:
    print("\t\t"+str(x))
  print("\n")


def showd(n, xs, desc):
  print("\n\tprinting first "+str(len(xs))+" items of "+str(len(xs))+" for "+desc+"\n" )
  i=0
  for k,v in xs.items():
    print("\t\t('"+str(k)+"', "+str(v)+")")
    i=i+1
    if i==n:
      break
  print("\n")


def dedupe(xs, desc):
  before = len(xs)
  xs = sorted(set(xs))
  print("deduped " +str(before - len(xs))+" from "+desc)
  return xs
      



def _load_and_process_metadata_craigcap(captions_dir, image_dir):
  """Loads image metadata from a directory containing CSV files and processes the captions.

  Args:
    captions_dir: Directory containing CSV files for each city containing caption annotations.
    image_dir: Directory containing subdirecties for each city with image files.

  Returns:
    A list of ImageMetadata.
  """
  image_metadata = []

  # take note!: we are only going to open the caption csv files for cities that are included in the craigcapImg directory. 
  # this allows us to (easily) run a subset of cities just by removing or adding subdirecties.
  id_to_filename = []
  ids = set()
  id_to_captions = {}


  for city in os.listdir(image_dir):

    if city == "summarycsv":
      continue

    with tf.gfile.FastGFile(os.path.join(captions_dir,city+".csv"), "r") as f:
      cityReader = csv.reader(f)
      

      # Extract the captions. Each image_id is associated with multiple captions.
      # seek back to first row
           
      for row in cityReader:
        if row[2] != "":
          image_id = row[2]
          caption = row[1]
          id_to_captions.setdefault(image_id, [])
          id_to_captions[image_id].append(caption)

      f.seek(0)
      # Extract the filenames.      
      # if you want to give each image a unique file name based on row even if it is a dup:
      # id_to_filename = [ (city+str(idx), os.path.join(city,row[2]+".jpg")) for idx, row in enumerate(cityReader)]
      
      for row in cityReader:
        x = row[2]
        if x != "":
          if x not in ids:
            ids.add(x)
            id_to_filename.append((x, os.path.join(city,x+".jpg")))

    print("\n\t+"+city+"\t\timgs: %d\t\tcaps: %d" % (len(id_to_filename),len(id_to_captions) ))


  id_to_filename = dedupe(id_to_filename,"id_to_filename")


  show(10, id_to_filename, "filenames")

  showd(10, id_to_captions, "captions")

  assert len(id_to_filename) == len(id_to_captions)
  assert set([x[0] for x in id_to_filename]) == set(id_to_captions.keys())
  print("Loaded caption metadata for %d images from %s and %s" % (len(id_to_filename), captions_dir, image_dir))

  # Process the captions and combine the data into a list of ImageMetadata.
  print("Processing captions.")
  
  num_captions = 0
  for image_id, base_filename in id_to_filename:
    filename = os.path.join(image_dir, base_filename)
    captions = [_process_caption(c) for c in id_to_captions[image_id]]
    image_metadata.append(ImageMetadata(image_id, filename, captions))
    num_captions += len(captions)
  print("Finished processing %d captions for %d images in %s and %s" %
        (num_captions, len(id_to_filename), captions_dir, image_dir))

  return image_metadata


def printFlags():
  print("\nthe flags that were passed to this python script:\n")
  for key, value in tf.flags.FLAGS.__flags.items():
    print("  "+'{:24}'.format(key)+ "\t:\t",value)
  print("")

def checkShards():
  def _is_valid_num_shards(num_shards):
    """Returns True if num_shards is compatible with FLAGS.num_threads."""
    return num_shards < FLAGS.num_threads or not num_shards % FLAGS.num_threads

  assert _is_valid_num_shards(FLAGS.train_shards), (
      "Please make the FLAGS.num_threads commensurate with FLAGS.train_shards")
  assert _is_valid_num_shards(FLAGS.val_shards), (
      "Please make the FLAGS.num_threads commensurate with FLAGS.val_shards")
  assert _is_valid_num_shards(FLAGS.test_shards), (
      "Please make the FLAGS.num_threads commensurate with FLAGS.test_shards")


def main(unused_argv):

  printFlags()

  checkShards()

  if not tf.gfile.IsDirectory(FLAGS.output_dir):
    tf.gfile.MakeDirs(FLAGS.output_dir)

  # Load image metadata from caption files.

  craigcap_dataset = _load_and_process_metadata_craigcap(FLAGS.craigcap_captions_dir, FLAGS.craigcap_image_dir)
  

  # Redistribute the craigcap data as follows:
  #   train_dataset = 80% of craigcap_dataset.
  #   val_dataset   = 10% of craigcap_dataset (for validation during training).
  #   test_dataset  = 10% of craigcap_dataset (for final evaluation).
  train_cutoff = int(0.8 * len(craigcap_dataset))
  val_cutoff = int(0.9 * len(craigcap_dataset))
  train_dataset = craigcap_dataset[0:train_cutoff]
  val_dataset = craigcap_dataset[train_cutoff:val_cutoff]
  test_dataset = craigcap_dataset[val_cutoff:]

  # Create vocabulary from the training captions.
  train_captions = [c for image in train_dataset for c in image.captions]
  vocab = _create_vocab(train_captions)

  _process_dataset("train", train_dataset, vocab, FLAGS.train_shards)
  _process_dataset("val", val_dataset, vocab, FLAGS.val_shards)
  _process_dataset("test", test_dataset, vocab, FLAGS.test_shards)


if __name__ == "__main__":
  tf.app.run()
