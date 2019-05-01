import pandas as pd
import requests
from bs4 import BeautifulSoup as bs4
import urllib
import csv
import os
import time
from datetime import datetime

def ifint(x):
    try: return(int(x.text[1:]))
    except: return
    
def ifimg(city,x):
    try:
        imagenumber = x.find( attrs={'class':'result-image gallery'}).get('data-ids').split(',')[0].split(':')[1]
        urllib.request.urlretrieve("https://images.craigslist.org/"+imagenumber+"_300x300.jpg", "/home/nooreen/CV/CL/"+city+'/'+imagenumber+".jpg")
        return(imagenumber)
    except: return
    
def parseresultrow(city, row):
    rowtext = row.find( attrs={'class':'result-title hdrlnk'}).text
    imagename = ifimg(city,row)
    price = ifint(row.find(attrs={'class':'result-price'}))
    return([city,rowtext, imagename, price])    
    
def getlistings(city, neighborhood, forReal):
    furniture = []
    url_base = 'https://'+city+'.craigslist.org/d/furniture/search'+neighborhood+'/fuo'
    print(str(datetime.now()))
    for i in range(19):
        print(i,end=" ")
        if forReal:
            params = dict(s=120*i)
            resp = requests.get(url_base, params=params)
            html = bs4(resp.text, 'html.parser')
            resultrows = html.find_all(attrs={'class':'result-row'})
            furniture.extend([parseresultrow(city,x) for x in resultrows])
    print("\n"+str(datetime.now()))
    return(furniture)
    
cldir = '/home/nooreen/CV/CL/'

def docity(city, forReal):
    print("\n"+city)

 #   if forReal:        
 #       os.mkdir(cldir+city)

    furniture = getlistings(city,'', forReal)
    
    if forReal:
        with open(cldir+'summarycsv/'+city+".csv","w", newline='') as f:
            writer = csv.writer(f)
            writer.writerows(furniture)


forReal = False
sleepSeconds= 60*3
zs = 20

with open("CLcitylist Left.txt") as h:
    for city in h.readlines():
        
        docity(city.strip(), forReal)

        for i in range(zs): 
            print("z",end="")
            time.sleep(sleepSeconds/zs)

        print("")

