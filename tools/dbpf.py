import struct,sys
def qfs(d):
    # d starts with 4-byte compressed size then 0x10FB
    i=4
    assert d[i]==0x10 and d[i+1]==0xFB,d[:8]
    size=(d[i+2]<<16)|(d[i+3]<<8)|d[i+4]; i+=5
    out=bytearray()
    while i<len(d):
        c=d[i]
        if c<0x80:
            b1=d[i+1]; pl=c&3; cl=((c&0x1c)>>2)+3; off=((c&0x60)<<3)+b1+1; i+=2
        elif c<0xC0:
            b1,b2=d[i+1],d[i+2]; pl=b1>>6; cl=(c&0x3f)+4; off=((b1&0x3f)<<8)+b2+1; i+=3
        elif c<0xE0:
            b1,b2,b3=d[i+1],d[i+2],d[i+3]; pl=c&3; cl=((c&0x0c)<<6)+b3+5; off=((c&0x10)<<12)+(b1<<8)+b2+1; i+=4
        elif c<0xFC:
            pl=((c&0x1f)<<2)+4; cl=0; off=0; i+=1
        else:
            pl=c&3; cl=0; off=0; i+=1
        out+=d[i:i+pl]; i+=pl
        for _ in range(cl): out.append(out[-off])
        if c>=0xFC: break
    return bytes(out)
def entries(path):
    d=open(path,'rb').read()
    assert d[:4]==b'DBPF'
    icount,ioff,isize=struct.unpack_from('<III',d,36)
    ents=[]
    for k in range(icount):
        t,g,ins,o,s=struct.unpack_from('<IIIII',d,ioff+20*k)
        ents.append((t,g,ins,d[o:o+s]))
    dirs={}
    for t,g,ins,b in ents:
        if t==0xE86B1EEF:
            for j in range(0,len(b),16):
                dirs[struct.unpack_from('<III',b,j)]=1
    res=[]
    for t,g,ins,b in ents:
        if (t,g,ins) in dirs or (len(b)>9 and b[4]==0x10 and b[5]==0xFB and t!=0xE86B1EEF and (t,g,ins) in dirs):
            b=qfs(b)
        res.append((t,g,ins,b))
    return res
TYPES={0x0B:'bool',0x01:'u8',0x02:'u16',0x03:'u32',0x07:'s32',0x08:'s64',0x09:'f32',0x0C:'str'}
def exemplar(b):
    if not (b[:4] in (b'EQZB',b'CQZB')): return None
    if b[4:8]!=b'1###': return ('text',b[:200])
    parent=struct.unpack_from('<III',b,8); n=struct.unpack_from('<I',b,20)[0]; i=24; props=[]
    for _ in range(n):
        pid,vt,kt=struct.unpack_from("<IHH",b,i); i+=8; vt>>=8
        fmt={0x01:'B',0x02:'H',0x03:'I',0x07:'i',0x08:'q',0x09:'f',0x0B:'?',0x0C:'c'}[vt]; sz=struct.calcsize('<'+fmt)
        if kt==0:
            i+=1; v=struct.unpack_from('<'+fmt,b,i)[0]; i+=sz; vals=[v]
        else:
            i+=1; cnt=struct.unpack_from('<I',b,i)[0]; i+=4
            if vt==0x0C: vals=[b[i:i+cnt].decode('latin1')]; i+=cnt
            else:
                vals=list(struct.unpack_from('<%d%s'%(cnt,fmt),b,i)); i+=cnt*sz
        props.append((pid,TYPES.get(vt,vt),vals))
    return parent,props
if __name__=='__main__':
    for t,g,ins,b in entries(sys.argv[1]):
        print('T=%08X G=%08X I=%08X len=%d'%(t,g,ins,len(b)))
        if t==0x6534284A:
            e=exemplar(b)
            if e and e[0]!='text':
                for pid,ty,v in e[1]:
                    vv=[('0x%08X'%x if isinstance(x,int) and ty in('u32',) else x) for x in v]
                    print('   0x%08X %s %s'%(pid,ty,vv))
