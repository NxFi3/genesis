"""Coordinate-seeded coherent terrain. Chunk order cannot change generated cells."""
import math


def value(seed, x, y):
    n=(seed*374761393+x*668265263+y*2147483647)&0xffffffff
    n=((n^(n>>13))*1274126177)&0xffffffff
    return (n^(n>>16))/4294967295


def noise(seed,x,y,scale):
    gx,gy=math.floor(x/scale),math.floor(y/scale)
    fx,fy=x/scale-gx,y/scale-gy
    fx=fx*fx*(3-2*fx);fy=fy*fy*(3-2*fy)
    return ((1-fx)*value(seed,gx,gy)+fx*value(seed,gx+1,gy))*(1-fy)+((1-fx)*value(seed,gx,gy+1)+fx*value(seed,gx+1,gy+1))*fy


def cell(seed,x,y,width,height):
    elevation=.6+3.8*noise(seed,x,y,32)+noise(seed+1,x,y,8)
    moisture=noise(seed+2,x,y,24)
    channel=width*.5+math.sin(y/19+seed)*width*.06+math.sin(y/7+seed)*1.8
    if abs(x-channel)<1.2:
        return 'river',round(.05-y/max(1,height-1)*.1,3)
    if elevation<1.5 and moisture>.62:return 'lake',-.1
    if elevation>4.3:return 'mountain',round(elevation-2,3)
    return ('forest' if moisture>.48 else 'plains'),round((elevation-2)*.35,3)


def chunk(seed,cx,cy,width,height,size=16):
    return [[cell(seed,x,y,width,height) for x in range(cx*size,min(width,(cx+1)*size))]
            for y in range(cy*size,min(height,(cy+1)*size))]


def generate(seed,width,height):
    terrain=[['plains']*width for _ in range(height)]
    heights=[[0.]*width for _ in range(height)]
    for cy in range(math.ceil(height/16)):
        for cx in range(math.ceil(width/16)):
            for dy,row in enumerate(chunk(seed,cx,cy,width,height)):
                for dx,(kind,h) in enumerate(row):
                    terrain[cy*16+dy][cx*16+dx]=kind;heights[cy*16+dy][cx*16+dx]=h
    return terrain,heights
