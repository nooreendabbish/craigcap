import pandas as pd
import requests
from bs4 import BeautifulSoup as bs4
import urllib
import csv

def ifint(x):
    try: return(int(x.text[1:]))
    except: return
    
def ifimg(x):
    try:
        imagenumber = x.find( attrs={'class':'result-image gallery'}).get('data-ids').split(',')[0].split(':')[1]
        urllib.request.urlretrieve("https://images.craigslist.org/"+imagenumber+"_300x300.jpg", imagenumber+".jpg")
        return(imagenumber)
    except: return
    
def parseresultrow(city, row):
    rowtext = row.find( attrs={'class':'result-title hdrlnk'}).text
    imagename = ifimg(row)
    price = ifint(row.find(attrs={'class':'result-price'}))
    return([city,rowtext, imagename, price])    
    
def getlistings(city, neighborhood):
    furniture = []
    url_base = 'https://'+city+'.craigslist.org/d/furniture/search'+neighborhood+'/fu0'
    for i in range(1):
        params = dict(s=120*i)
        resp = requests.get(url_base, params=params)
        html = bs4(resp.text, 'html.parser')
        resultrows = html.find_all(attrs={'class':'result-row'})
        furniture.extend([parseresultrow(city,x) for x in resultrows)
    print(furniture)
    
city = 'philadelphia'
furniture = getlistings(city,'')


###    urllib.request.urlretrieve("https://images.craigslist.org/"
