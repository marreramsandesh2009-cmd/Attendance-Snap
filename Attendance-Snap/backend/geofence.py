import math
def distance(lat1,lon1,lat2,lon2):
 r=6371000;p1=math.radians(lat1);p2=math.radians(lat2);dp=math.radians(lat2-lat1);dl=math.radians(lon2-lon1)
 a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
 return 2*r*math.asin(math.sqrt(a))
def check(lat,lon,accuracy,clat,clon,radius,max_accuracy):
 if not all(math.isfinite(x) for x in (lat,lon,accuracy)) or not(-90<=lat<=90 and -180<=lon<=180): return False,None,'Invalid GPS values.'
 if accuracy<=0 or accuracy>max_accuracy:return False,None,f'GPS accuracy must be {max_accuracy} m or better.'
 d=distance(lat,lon,clat,clon)
 if d+accuracy>radius:return False,d,f'Outside permitted campus area or GPS accuracy is insufficient. Distance: {round(d)} m.'
 return True,d,'Location accepted.'
