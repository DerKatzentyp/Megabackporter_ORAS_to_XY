import struct
def parse(d):
    assert d[:4]==b'CRAG'
    hdr_sz,bom,ver,chunks,dat_off,file_sz,largest=struct.unpack_from('<IHHIIII',d,4)
    p=hdr_sz; assert d[p:p+4]==b'OTAF'
    fato_sz,cnt,pad=struct.unpack_from('<IHH',d,p+4)
    offs=list(struct.unpack_from('<%dI'%cnt,d,p+12))
    fato=(fato_sz,cnt,pad,offs)
    p+=fato_sz; assert d[p:p+4]==b'BTAF'
    fatb_sz,n=struct.unpack_from('<II',d,p+4)
    fatb=p+12
    fimb=p+fatb_sz; assert d[fimb:fimb+4]==b'BMIF'
    fimb_hdr,fimb_datasz=struct.unpack_from('<II',d,fimb+4)
    data=fimb+fimb_hdr
    ent=[]
    for i in range(cnt):
        e=fatb+offs[i]
        vec=struct.unpack_from('<I',d,e)[0]
        q=e+4; subs=[]
        for b in range(32):
            if vec>>b & 1:
                st,en,ln=struct.unpack_from('<III',d,q); q+=12
                subs.append((b,d[data+st:data+st+ln],en-st))
        ent.append((vec,subs))
    return dict(hdr_sz=hdr_sz,bom=bom,ver=ver,chunks=chunks,fimb_hdr=fimb_hdr,
                pad=pad,entries=ent)
def build(g):
    ent=g['entries']; cnt=len(ent)
    offs=[]; fatb_body=bytearray(); data=bytearray()
    for vec,subs in ent:
        offs.append(len(fatb_body))
        fatb_body+=struct.pack('<I',vec)
        for b,blob,padded in subs:
            st=len(data)
            data+=blob
            while len(data)%4: data+=b'\x00'
            en=st+padded if padded>=len(blob) else len(data)-st
            en=st+(len(data)-st)   # padded end
            fatb_body+=struct.pack('<III',st,en,len(blob))
    fato_sz=12+4*cnt
    fatb_sz=12+len(fatb_body)
    out=bytearray()
    out+=b'CRAG'+struct.pack('<IHHIIII',0x1C,g['bom'],g['ver'],g['chunks'],0,0,0)
    out+=b'OTAF'+struct.pack('<IHH',fato_sz,cnt,g['pad'])+struct.pack('<%dI'%cnt,*offs)
    out+=b'BTAF'+struct.pack('<II',fatb_sz,cnt)+fatb_body
    dat_off=len(out)+g['fimb_hdr']
    out+=b'BMIF'+struct.pack('<II',g['fimb_hdr'],len(data))+b'\x00'*(g['fimb_hdr']-12)
    out+=data
    largest=max((len(b) for _,s in ent for _,b,_ in s), default=0)
    largest=(largest+3)&~3
    struct.pack_into('<III',out,0x10,dat_off,len(out),largest)
    return bytes(out)
