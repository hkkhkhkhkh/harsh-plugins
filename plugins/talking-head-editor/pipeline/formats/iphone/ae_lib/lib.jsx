// EF motion-graphics scene library (After Effects 2026, ExtendScript). Brand: Ink/Paper, Archivo only, radius 14/10/8/6.
// Every scene = one 1080x1920 comp with alpha, rendered to ProRes 4444. Times in scene JSON are record seconds;
// t(x) converts to comp time. Motion: rise-in 18-22 px with exponential ease, masks/lines draw on, no bounce.
var INK="#10243D", DEEP="#1D3A57", BODY="#2E4A66", MUTED="#45607C", DIM="#B9C9D8", RULE="#CFD9E1", PAPER="#F7F9FB", RED="#BE2A1B", GREEN="#10604F", NIGHT="#0B1A2C";
var FB="ArchivoEF-Bold", FS="ArchivoEF-SemiBold", FM="ArchivoEF-Medium";
function hex(h){return [parseInt(h.substr(1,2),16)/255, parseInt(h.substr(3,2),16)/255, parseInt(h.substr(5,2),16)/255];}
function easeAll(prop, inf){ inf = inf||80; for (var k=1;k<=prop.numKeys;k++){ var d=(prop.value instanceof Array)?prop.value.length:1; var a=[],b=[];
  for (var i=0;i<d;i++){a.push(new KeyframeEase(0,inf)); b.push(new KeyframeEase(0,inf));} try{prop.setTemporalEaseAtKey(k,a,b);}catch(e){} } }
function rect(comp,name,cx,cy,w,h,fill,stroke,r,sw){ var L=comp.layers.addShape(); L.name=name;
  var g=L.property("Contents").addProperty("ADBE Vector Group"); var rc=g.property("Contents").addProperty("ADBE Vector Shape - Rect");
  rc.property("Size").setValue([w,h]); rc.property("Roundness").setValue(r||0);
  if(stroke){var s=g.property("Contents").addProperty("ADBE Vector Graphic - Stroke"); s.property("Color").setValue(hex(stroke)); s.property("Stroke Width").setValue(sw||2);}
  if(fill){var f=g.property("Contents").addProperty("ADBE Vector Graphic - Fill"); f.property("Color").setValue(hex(fill));}
  L.property("Transform").property("Position").setValue([cx,cy]); return L; }
function ellipse(comp,name,cx,cy,d,fill,stroke,sw){ var L=comp.layers.addShape(); L.name=name;
  var g=L.property("Contents").addProperty("ADBE Vector Group"); var e=g.property("Contents").addProperty("ADBE Vector Shape - Ellipse"); e.property("Size").setValue([d,d]);
  if(stroke){var s=g.property("Contents").addProperty("ADBE Vector Graphic - Stroke"); s.property("Color").setValue(hex(stroke)); s.property("Stroke Width").setValue(sw||3);}
  if(fill){var f=g.property("Contents").addProperty("ADBE Vector Graphic - Fill"); f.property("Color").setValue(hex(fill));}
  L.property("Transform").property("Position").setValue([cx,cy]); return L; }
function path(comp,name,pts,col,w,closed){ var L=comp.layers.addShape(); L.name=name;
  var g=L.property("Contents").addProperty("ADBE Vector Group"); var p=g.property("Contents").addProperty("ADBE Vector Shape - Group");
  var s=new Shape(); s.vertices=pts; s.closed=!!closed; p.property("Path").setValue(s);
  var st=g.property("Contents").addProperty("ADBE Vector Graphic - Stroke"); st.property("Color").setValue(hex(col)); st.property("Stroke Width").setValue(w); st.property("Line Cap").setValue(2);
  var tr=g.property("Contents").addProperty("ADBE Vector Filter - Trim");
  L.property("Transform").property("Position").setValue([0,0]); L.property("Transform").property("Anchor Point").setValue([0,0]); return {layer:L, trim:tr}; }
function draw(pth,t0,dur){ var e=pth.trim.property("End"); e.setValueAtTime(0,0); e.setValueAtTime(Math.max(0,t0),0); e.setValueAtTime(t0+(dur||0.35),100); easeAll(e,70);
  if(t0>0.05){ var o=pth.layer.property("Transform").property("Opacity"); o.setValueAtTime(0,0); o.setValueAtTime(t0-0.01,0); o.setValueAtTime(t0,100); } } // round caps draw a dot at zero length
function text(comp,str,font,size,col,x,y,just,track,lead){ var L=comp.layers.addText(str); var tp=L.property("Source Text"); var d=tp.value;
  d.resetCharStyle(); d.font=font; d.fontSize=size; d.fillColor=hex(col); d.applyFill=true; d.applyStroke=false;
  d.justification = just||ParagraphJustification.CENTER_JUSTIFY; if(track) d.tracking=track; if(lead){d.autoLeading=false; d.leading=lead;}
  tp.setValue(d); L.property("Transform").property("Position").setValue([x,y]); return L; }
function L_(){return ParagraphJustification.LEFT_JUSTIFY;} function R_(){return ParagraphJustification.RIGHT_JUSTIFY;}
function fadeIn(L,t,dur){ var o=L.property("Transform").property("Opacity"); o.setValueAtTime(Math.max(0,t-0.04),0); o.setValueAtTime(t,0); o.setValueAtTime(t+(dur||0.3),100); easeAll(o,60); }
function reveal(L,t,rise,dur){ var o=L.property("Transform").property("Opacity"), p=L.property("Transform").property("Position"); var v=p.value; dur=dur||0.5; rise=(rise===undefined)?20:rise;
  o.setValueAtTime(Math.max(0,t-0.04),0); o.setValueAtTime(t,0); o.setValueAtTime(t+dur*0.6,100);
  p.setValueAtTime(t,[v[0],v[1]+rise]); p.setValueAtTime(t+dur,[v[0],v[1]]); easeAll(p,85); easeAll(o,60); }
function pop(L,t,from){ var s=L.property("Transform").property("Scale"); var o=L.property("Transform").property("Opacity"); from=from||60;
  o.setValueAtTime(Math.max(0,t-0.04),0); o.setValueAtTime(t,0); o.setValueAtTime(t+0.18,100);
  s.setValueAtTime(t,[from,from]); s.setValueAtTime(t+0.42,[100,100]); easeAll(s,85); }
function hide(L,t,dur){ var o=L.property("Transform").property("Opacity"); var cur=o.numKeys?o.valueAtTime(t,false):100; o.setValueAtTime(t,cur); o.setValueAtTime(t+(dur||0.25),0); }
function hideAll(arr,t){ for(var i=0;i<arr.length;i++) hide(arr[i],t); }
function grid(comp){ var L=comp.layers.addShape(); L.name="grid"; var root=L.property("Contents");
  for(var x=60;x<1080;x+=60){var g=root.addProperty("ADBE Vector Group"); var p=g.property("Contents").addProperty("ADBE Vector Shape - Group"); var s=new Shape(); s.vertices=[[x,0],[x,1920]]; s.closed=false; p.property("Path").setValue(s);
    var st=g.property("Contents").addProperty("ADBE Vector Graphic - Stroke"); st.property("Color").setValue(hex(DIM)); st.property("Stroke Width").setValue(1); st.property("Opacity").setValue(7);}
  for(var y=60;y<1920;y+=60){var g2=root.addProperty("ADBE Vector Group"); var p2=g2.property("Contents").addProperty("ADBE Vector Shape - Group"); var s2=new Shape(); s2.vertices=[[0,y],[1080,y]]; s2.closed=false; p2.property("Path").setValue(s2);
    var st2=g2.property("Contents").addProperty("ADBE Vector Graphic - Stroke"); st2.property("Color").setValue(hex(DIM)); st2.property("Stroke Width").setValue(1); st2.property("Opacity").setValue(7);}
  L.property("Transform").property("Position").setValue([0,0]); L.property("Transform").property("Anchor Point").setValue([0,0]); return L; }
// full-screen Ink background that wipes up in and down out (L3 explainer scenes)
function fullBg(comp,t0,t1,hardIn,hardOut){ var bg=rect(comp,"bg",540,960,1080,1920,NIGHT,null,0); var gd=grid(comp);
  var p=bg.property("Transform").property("Position");
  gd.parent=bg; gd.property("Transform").property("Position").setValue([-540,-960]);
  if(!hardIn){ p.setValueAtTime(t0,[540,960+1920]); p.setValueAtTime(t0+0.5,[540,960]); }
  if(t1!==null && !hardOut){ p.setValueAtTime(t1-0.45,[540,960]); p.setValueAtTime(t1,[540,960-1920]); }
  if(p.numKeys) easeAll(p,90); return bg; }
// split plate: Ink everywhere except a rounded window at the top where the A-roll shows through (L2)
function splitPlate(comp,t0,t1,win,hardIn,hardOut){ var L=comp.layers.addShape(); L.name="plate"; var root=L.property("Contents");
  var g=root.addProperty("ADBE Vector Group"); var c=g.property("Contents");
  var outer=c.addProperty("ADBE Vector Shape - Rect"); outer.property("Size").setValue([1080,1920]); outer.property("Position").setValue([540,960]);
  c.addProperty("ADBE Vector Shape - Rect");
  var mp=c.addProperty("ADBE Vector Filter - Merge"); mp.property("Mode").setValue(3); // subtract
  var f=c.addProperty("ADBE Vector Graphic - Fill"); f.property("Color").setValue(hex(NIGHT));
  // AE invalidates property handles when the group changes: fetch the hole's properties only after the group is complete
  var hole=L.property("Contents").property(1).property("Contents").property(2); var hs=hole.property("Size"), hp=hole.property("Position"), hr=hole.property("Roundness");
  L.property("Transform").property("Anchor Point").setValue([0,0]); L.property("Transform").property("Position").setValue([0,0]); // content coords = comp coords
  var ti=hardIn?t0:t0+0.55, to=hardOut?t1:t1-0.5;
  if(!hardIn){ hs.setValueAtTime(t0,[1080,1920]); hp.setValueAtTime(t0,[540,960]); hr.setValueAtTime(t0,0); }
  hs.setValueAtTime(ti,[win.w,win.h]); hp.setValueAtTime(ti,[540,win.y+win.h/2]); hr.setValueAtTime(ti,28);
  hs.setValueAtTime(to,[win.w,win.h]); hp.setValueAtTime(to,[540,win.y+win.h/2]); hr.setValueAtTime(to,28);
  if(!hardOut){ hs.setValueAtTime(t1,[1080,1920]); hp.setValueAtTime(t1,[540,960]); hr.setValueAtTime(t1,0); }
  easeAll(hs,88); easeAll(hp,88); easeAll(hr,88);
  var border=rect(comp,"winborder",540,win.y+win.h/2,win.w,win.h,null,"#2E4A66",28,2); if(!hardIn) fadeIn(border,ti-0.05,0.2); if(!hardOut) hide(border,to-0.05,0.1);
  return L; }
function importImg(file){ var io=new ImportOptions(File(file)); return app.project.importFile(io); }
function eyebrow(comp,txt,x,y,t,col){ var ln=path(comp,"eb-line",[[x,y-9],[x+46,y-9]],RED,3); draw(ln,t,0.3);
  var L=text(comp,txt.toUpperCase(),FM,26,col||DIM,x+62,y,L_(),150); reveal(L,t+0.05,10,0.4); return [ln.layer,L]; }
function tick(comp,x,y,t){ var p=path(comp,"tick",[[x-14,y],[x-4,y+11],[x+16,y-12]],"#3FA37F",6); draw(p,t,0.25); return p.layer; }

// ---------------- scene builders ----------------
function sc_title(comp,s,t){ var c=s.cues; var a=eyebrow(comp,s.eyebrow,72,190,t(c.in),PAPER);
  var big=text(comp,s.text,FB,s.size||150,PAPER,68,340,L_(),-40); reveal(big,t(c.in)+0.08,26,0.6);
  big.property("Effects").addProperty("ADBE Drop Shadow").property("Opacity").setValue(60);
  hideAll(a.concat([big]),t(c.out)); }
function sc_chips(comp,s,t){ var c=s.cues, items=s.items, L=[], y=s.y||170, rowH=100, maxW=960, rows=[[]], w=0;
  for(var i=0;i<items.length;i++){ var ww=items[i][0].length*23+64; if(w+ww>maxW && rows[rows.length-1].length){rows.push([]); w=0;} rows[rows.length-1].push([items[i],ww]); w+=ww+16; }
  for(var r=0;r<rows.length;r++){ var tot=0; for(var k=0;k<rows[r].length;k++) tot+=rows[r][k][1]; tot+=16*(rows[r].length-1); var x=540-tot/2;
    for(var k2=0;k2<rows[r].length;k2++){ var it=rows[r][k2][0], ww2=rows[r][k2][1], cx=x+ww2/2, cy=y+r*rowH;
      var R=rect(comp,"chip",cx,cy,ww2,78,INK,null,10); var T=text(comp,it[0],FS,40,PAPER,cx,cy+14); pop(R,t(it[1]),70); pop(T,t(it[1]),70); L.push(R,T); x+=ww2+16; } }
  if(s.sub){ var sy=y+rows.length*rowH-4; var SR=rect(comp,"sub",540,sy,s.sub[0].length*15+50,48,PAPER,null,6); var ST=text(comp,s.sub[0].toUpperCase(),FM,24,INK,540,sy+9,null,120);
    reveal(SR,t(s.sub[1]),10,0.35); reveal(ST,t(s.sub[1]),10,0.35); L.push(SR,ST); }
  hideAll(L,t(c.out)); }
function molecule(comp,kind,cx,cy,t0,col){ var out=[];
  if(kind=="oxide"){ var a=ellipse(comp,"m1",cx-60,cy,112,null,col,4); var b=ellipse(comp,"m2",cx+70,cy,78,null,col,4); var ln=path(comp,"bond",[[cx-4,cy],[cx+31,cy]],col,4);
    var ta=text(comp,"Mg",FB,40,PAPER,cx-60,cy+14); var tb=text(comp,"O",FB,36,PAPER,cx+70,cy+13); pop(a,t0); pop(b,t0+0.08); draw(ln,t0+0.12,0.2); pop(ta,t0); pop(tb,t0+0.08); out=[a,b,ln.layer,ta,tb]; }
  else { var m=ellipse(comp,"m",cx,cy,96,null,col,4); var tm=text(comp,kind=="fe"?"Fe":"Mg",FB,36,PAPER,cx,cy+13);
    var l1=path(comp,"g1",[[cx-48,cy],[cx-100,cy-50],[cx-150,cy-40]],DIM,3); var l2=path(comp,"g2",[[cx+48,cy],[cx+100,cy+50],[cx+150,cy+40]],DIM,3);
    var g1=text(comp,"glycine",FM,22,DIM,cx-150,cy-60); var g2=text(comp,"glycine",FM,22,DIM,cx+150,cy+78);
    pop(m,t0); pop(tm,t0); draw(l1,t0+0.1,0.3); draw(l2,t0+0.1,0.3); fadeIn(g1,t0+0.3); fadeIn(g2,t0+0.3); out=[m,tm,l1.layer,l2.layer,g1,g2]; }
  return out; }
function sc_mineral(comp,s,t){ var c=s.cues, T0=t(s.start), T1=t(s.end); fullBg(comp,T0,T1,s.hard_in,s.hard_out);
  var h=text(comp,"Same mineral.\rDifferent molecule.",FB,88,PAPER,68,370,L_(),-40,92); reveal(h,T0+0.3,24,0.55);
  var cards=[], xs=[290,790];
  for(var i=0;i<2;i++){ var cd=rect(comp,"card"+i,xs[i],1010,470,640,i?"#16304B":"#122a44",i?DIM:"#2E4A66",14,i?2:1); reveal(cd,T0+0.45+i*0.1,24,0.5); cards.push(cd); }
  // phase A: magnesium
  var nA=[text(comp,"FORM A",FM,22,DIM,90,760,L_(),150), text(comp,"Magnesium\roxide",FB,52,PAPER,90,830,L_(),-20,56),
          text(comp,"FORM B",FM,22,DIM,590,760,L_(),150), text(comp,"Magnesium\rbisglycinate",FB,52,PAPER,590,830,L_(),-20,56)];
  for(var k=0;k<nA.length;k++) reveal(nA[k],T0+0.55+(k>1?0.1:0),14,0.45);
  var mA=molecule(comp,"oxide",290,1040,t(c.oxide),DIM).concat(molecule(comp,"bis",790,1040,t(c.bis),PAPER));
  var bl=[text(comp,"Absorption",FM,26,DIM,90,1215,L_()), text(comp,"Absorption",FM,26,DIM,590,1215,L_())];
  var tr1=rect(comp,"tr1",290,1250,390,14,DEEP,null,7), tr2=rect(comp,"tr2",790,1250,390,14,DEEP,null,7);
  var b1=path(comp,"bar1",[[95,1250],[150,1250]],RED,14), b2=path(comp,"bar2",[[595,1250],[850,1250]],"#3FA37F",14);
  fadeIn(bl[0],t(c.bis)+0.2); fadeIn(bl[1],t(c.bis)+0.2); fadeIn(tr1,t(c.bis)+0.2); fadeIn(tr2,t(c.bis)+0.2); draw(b1,t(c.bis)+0.35,0.5); draw(b2,t(c.bis)+0.45,0.8);
  var note=text(comp,"Schematic. Forms differ in how much is absorbed.",FM,24,"#8AA0B6",72,1400,L_()); fadeIn(note,t(c.bis)+0.5);
  var phaseA=nA.concat(mA).concat(bl).concat([tr1,tr2,b1.layer,b2.layer,note]);
  if(c.iron){ hideAll(phaseA,t(c.iron)-0.25);
    var nB=[text(comp,"FORM A",FM,22,DIM,90,760,L_(),150), text(comp,"Iron\rascorbate",FB,52,PAPER,90,830,L_(),-20,56),
            text(comp,"FORM B",FM,22,DIM,590,760,L_(),150), text(comp,"Iron\rbisglycinate",FB,52,PAPER,590,830,L_(),-20,56)];
    for(var k3=0;k3<nB.length;k3++) reveal(nB[k3],t(c.iron),14,0.4);
    var fa=ellipse(comp,"fe1",290,1040,110,null,DIM,4); var fat=text(comp,"Fe",FB,40,PAPER,290,1054); var asc=text(comp,"+ ascorbate",FM,26,DIM,290,1140); pop(fa,t(c.iron)+0.1); pop(fat,t(c.iron)+0.1); fadeIn(asc,t(c.iron)+0.3);
    var mB=molecule(comp,"fe",790,1040,t(c.iron2),PAPER);
    var nt2=text(comp,"Different form. Different absorption and tolerance.",FM,24,"#8AA0B6",72,1400,L_()); fadeIn(nt2,t(c.iron2)+0.3); }
}
function sc_rxpad(comp,s,t){ var c=s.cues, T0=t(s.start), T1=t(s.end); fullBg(comp,T0,T1,s.hard_in,s.hard_out);
  var pad=rect(comp,"pad",540,560,820,640,"#FBF9F4",null,14); var rx=text(comp,"Rx",FB,64,INK,180,340,L_()); var ad=text(comp,"ADVICE GIVEN",FM,22,"#8AA0B6",900,330,R_(),120);
  var rule=path(comp,"rule",[[170,370],[910,370]],RULE,2);
  var grp=[pad,rx,ad,rule.layer]; for(var i=0;i<grp.length;i++){ if(grp[i]!==pad) grp[i].parent=pad; }
  rx.property("Transform").property("Position").setValue([-360,-220]); ad.property("Transform").property("Position").setValue([360,-230]); rule.layer.property("Transform").property("Position").setValue([-540,-560]);
  var pr=pad.property("Transform").property("Rotation"); pr.setValueAtTime(T0+0.2,-8); pr.setValueAtTime(T0+0.75,-2); easeAll(pr,85);
  reveal(pad,T0+0.2,300,0.6);
  var lines=s.lines, hand=[];
  for(var k=0;k<lines.length;k++){ var y=480+k*110; var L=text(comp,lines[k][0],"Noteworthy-Bold",62,"#1D3A57",200,y,L_());
    try{ L.property("Source Text").value.font; }catch(e){}
    fadeIn(L,t(lines[k][1]),0.25); var sk=path(comp,"strike"+k,[[190,y-18],[190+lines[k][0].length*30,y-24]],RED,7); draw(sk,t(lines[k][1])+0.45,0.3); hand.push(L,sk.layer); }
}
// split scenes: plate + panel content in y 1210..1720
var WIN={w:560,h:560,y:70};   // square box in the upper third (Harsh, 27 Sep); the A-roll is transformed in Resolve so his face sits in its centre
function wrap2(txt){ if(txt.length<=18) return txt; var m=Math.floor(txt.length/2), best=-1; for(var i=0;i<txt.length;i++){ if(txt.charAt(i)==" " && (best<0 || Math.abs(i-m)<Math.abs(best-m))) best=i; } return best<0?txt:txt.substr(0,best)+"\r"+txt.substr(best+1); }
function panelTitle(comp,txt,t,full){ var L=full?text(comp,wrap2(txt),FB,74,PAPER,540,470,null,-40,80):text(comp,txt,FB,48,PAPER,90,700,L_(),-30); reveal(L,t,16,0.5); return [L]; }
function sc_split(comp,s,t){ var c=s.cues, T0=t(s.start), T1=t(s.end); var P=[];
  if(s.full) fullBg(comp,T0,T1,s.hard_in,s.hard_out); else splitPlate(comp,T0,T1,WIN,s.hard_in,s.hard_out);
  P=P.concat(panelTitle(comp,s.title,T0+(s.hard_in?0.1:0.45),s.full));
  var n0=comp.numLayers;   // everything built below is panel content; in full-screen mode it is scaled up and centred
  var v=s.variant, items=s.items||[];
  if(v=="steps"){ for(var i=0;i<items.length;i++){ var x=90+i*305; var R=rect(comp,"st"+i,x+140,870,280,190,"#122a44","#2E4A66",10,1); var n=text(comp,String(i+1),FM,26,DIM,x+26,810,L_()); var tt=text(comp,items[i][0],FB,38,PAPER,x+26,880,L_(),-10,44);
      reveal(R,t(items[i][1]),18,0.45); reveal(n,t(items[i][1])+0.05,12,0.4); reveal(tt,t(items[i][1])+0.08,12,0.4);
      if(i>0){ var ar=path(comp,"ar"+i,[[x-22,870],[x-4,870]],DIM,3); draw(ar,t(items[i][1]),0.2); } } }
  if(v=="checklist" || v=="stack"){ for(var j=0;j<items.length;j++){ var y=800+j*105; var dv=path(comp,"dv"+j,[[90,y-52],[990,y-52]],DEEP,2); draw(dv,t(items[j][1]),0.3);
      var tx=s.full?text(comp,items[j][0],FB,60,PAPER,540,y+12,null,-20):text(comp,items[j][0],FB,52,PAPER,v=="checklist"?150:90,y+10,L_(),-20); reveal(tx,t(items[j][1]),14,0.4); if(v=="checklist" && !s.full) tick(comp,110,y-6,t(items[j][1])+0.1); } }
  if(v=="twocol"){ var lc=rect(comp,"lc",310,880,420,280,"#122a44","#2E4A66",10,1), rc=rect(comp,"rc",770,880,420,280,"#16304B",DIM,10,2);
    var lt=text(comp,"Theory",FB,54,PAPER,310,895), rt=text(comp,"Practical\rapplication",FB,50,PAPER,770,870,null,-20,54);
    reveal(lc,t(c.a),18,0.45); reveal(lt,t(c.a),18,0.45); var sk=path(comp,"sk",[[200,880],[420,880]],RED,7); draw(sk,t(c.strike),0.3);
    var lo=lt.property("Transform").property("Opacity"); lo.setValueAtTime(t(c.strike)+0.2,100); lo.setValueAtTime(t(c.strike)+0.5,45);
    reveal(rc,t(c.b),18,0.45); reveal(rt,t(c.b),18,0.45); var gl=path(comp,"gl",[[600,1005],[940,1005]],"#3FA37F",6); draw(gl,t(c.b)+0.3,0.4); }
  if(v=="mech"){ var nodes=items; var xs=[200,540,880];
    for(var m=0;m<nodes.length;m++){ var nd=ellipse(comp,"n"+m,xs[m],870,200,"#122a44",m==nodes.length-1?"#3FA37F":DIM,3); var nt=text(comp,nodes[m][0],FS,28,PAPER,xs[m],880,null,-10,32);
      pop(nd,t(nodes[m][1])); pop(nt,t(nodes[m][1])); if(m>0){ var ar2=path(comp,"a"+m,[[xs[m-1]+105,870],[xs[m]-105,870]],DIM,3); draw(ar2,t(nodes[m][1])-0.05,0.3); } } }
  if(v=="dial"){ var cx=540, cy=990, r=210; var arc=path(comp,"arc",[[cx-r,cy],[cx-r*0.7,cy-r*0.7],[cx,cy-r],[cx+r*0.7,cy-r*0.7],[cx+r,cy]],DEEP,16); draw(arc,T0+0.4,0.6);
    var nd2=path(comp,"needle",[[cx,cy],[cx,cy-r+30]],PAPER,6); draw(nd2,T0+0.6,0.2);
    var rot=nd2.layer.property("Transform").property("Rotation"); nd2.layer.property("Transform").property("Anchor Point").setValue([cx,cy]); nd2.layer.property("Transform").property("Position").setValue([cx,cy]);
    rot.setValueAtTime(T0+0.6,-70); rot.setValueAtTime(T0+1.2,25); rot.setValueAtTime(T0+1.9,-15); rot.setValueAtTime(T0+2.5,5); easeAll(rot,70);
    var kc=text(comp,"kcal",FM,30,DIM,cx,cy+50); fadeIn(kc,T0+0.6); }
  if(v=="ladder"){ var cardsL=[]; for(var q=0;q<items.length;q++){ var yy=780+q*92; var cR=rect(comp,"lad"+q,540,yy,860,78,"#122a44","#2E4A66",10,1); var cT=text(comp,items[q][0],FS,36,PAPER,140,yy+13,L_()); 
      reveal(cR,t(items[q][1]),16,0.4); reveal(cT,t(items[q][1]),16,0.4); cardsL.push(cR,cT); }
    var bigS=path(comp,"bigstrike",[[120,1090],[960,730]],RED,8); draw(bigS,t(c.strike),0.35);
    hideAll(cardsL.concat([bigS.layer]),t(c.collapse)-0.2);
    var one=rect(comp,"one",540,880,900,220,INK,DIM,14,2); var oT=text(comp,"All of nutrition.\rOne course.",FB,62,PAPER,540,860,null,-30,66); reveal(one,t(c.collapse),24,0.5); reveal(oT,t(c.collapse)+0.05,24,0.5);
    if(c.bonus){ var bt=text(comp,"Medical modules included",FM,32,DIM,540,1050); reveal(bt,t(c.bonus),10,0.45); } }
  if(v=="bonus"){ var mc=rect(comp,"mod",540,900,900,300,"#122a44",DIM,14,2); reveal(mc,T0+0.5,20,0.5);
    var mt=text(comp,"Medical nutrition\rmodule",FB,58,PAPER,120,890,L_(),-30,62); reveal(mt,t(c.a)+0.05,14,0.45);
    if(c.b){ var sub=text(comp,"Built around specific medical cases",FM,30,DIM,120,1010,L_()); reveal(sub,t(c.b),10,0.4); } }
  if(s.full){ var k=comp.numLayers-n0; var nl=comp.layers.addNull(); nl.name="fullscale"; nl.property("Transform").property("Anchor Point").setValue([540,900]);
    nl.property("Transform").property("Position").setValue([540,1010]); nl.property("Transform").property("Scale").setValue([108,108]);
    for(var z=2; z<=k+1; z++){ comp.layer(z).setParentWithJump(nl); } }
}
function sc_seal(comp,s,t){ var c=s.cues; var g=ellipse(comp,"seal",540,300,330,INK,PAPER,6); var n=text(comp,s.big||"7",FB,120,PAPER,540,300,null);
  var d=text(comp,s.mid||"DAY",FS,32,PAPER,540,345,null,80); var low=text(comp,"",FM,22,DIM,540,390,null,150);
  var grp=[n,d,low]; for(var i=0;i<grp.length;i++){ grp[i].parent=g; } n.property("Transform").property("Position").setValue([0,10]); d.property("Transform").property("Position").setValue([0,55]); low.property("Transform").property("Position").setValue([0,100]);
  var sc=g.property("Transform").property("Scale"), ro=g.property("Transform").property("Rotation"), op=g.property("Transform").property("Opacity");
  op.setValueAtTime(t(c.in)-0.04,0); op.setValueAtTime(t(c.in),100); sc.setValueAtTime(t(c.in),[165,165]); sc.setValueAtTime(t(c.in)+0.16,[96,96]); sc.setValueAtTime(t(c.in)+0.3,[100,100]);
  ro.setValueAtTime(t(c.in),-24); ro.setValueAtTime(t(c.in)+0.16,-8);
  var lt=low.property("Source Text");
  if(c.count){ lt.expression='var a='+t(c.count).toFixed(3)+'; var p=Math.round(linear(time,a,a+0.8,0,100)); time<a?"'+(s.low||"")+'":p+"% REFUND";'; }
  else { var dd=lt.value; dd.text=s.low||"100% REFUND"; lt.setValue(dd); }
  hide(g,t(c.out),0.3); }
function sc_price(comp,s,t){ var c=s.cues, y=s.y||1470; var card=rect(comp,"card",540,y,780,190,INK,null,14); reveal(card,t(c.in),20,0.5);
  var l1=text(comp,"ANNUAL",FM,22,DIM,230,y-40,L_(),150); var p1=text(comp,"",FB,72,PAPER,230,y+40,L_(),-30); reveal(l1,t(c.in)+0.05,10,0.4); reveal(p1,t(c.in)+0.05,10,0.4);
  var a=t(c.annual); p1.property("Source Text").expression='var a='+a.toFixed(3)+'; var v=Math.round(linear(time,a,a+0.7,0,18000)/100)*100; "₹"+(v>=1000?Math.floor(v/1000)+","+("00"+(v%1000)).slice(-3):v);';
  if(c.monthly){ var dv=rect(comp,"dv",560,y,2,110,DEEP,null,0); fadeIn(dv,t(c.monthly)); var l2=text(comp,"OR MONTHLY",FM,22,DIM,610,y-40,L_(),150); var p2=text(comp,"₹1,999",FB,72,PAPER,610,y+40,L_(),-30); reveal(l2,t(c.monthly),10,0.4); reveal(p2,t(c.monthly),10,0.4); }
  if(c.year){ var yr=text(comp,"a year",FM,26,DIM,230+300,y+40,L_()); fadeIn(yr,t(c.annual)+0.7); }
}
function sc_cta(comp,s,t){ var c=s.cues, y=s.y||1470; var b=rect(comp,"btn",540,y,780,124,INK,null,8); var tx=text(comp,s.text||"Click the link below",FS,54,PAPER,505,y+19); var ar=text(comp,"↓",FB,56,PAPER,845,y+20);
  reveal(b,t(c.in),22,0.5); reveal(tx,t(c.in)+0.04,22,0.5); reveal(ar,t(c.in)+0.08,22,0.5);
  var p=ar.property("Transform").property("Position"); for(var k=0;k<4;k++){ var tt=t(c.in)+0.7+k*0.55; p.setValueAtTime(tt,[845,y+20]); p.setValueAtTime(tt+0.25,[845,y+32]); p.setValueAtTime(tt+0.5,[845,y+20]); } }
function sc_badge(comp,s,t){ var c=s.cues; var g=rect(comp,"cert",540,260,620,150,INK,DIM,14,2); reveal(g,t(c.in),22,0.5);
  var ic=ellipse(comp,"ic",330,260,78,null,"#3FA37F",4); var tk=tick(comp,330,262,t(c.in)+0.35); pop(ic,t(c.in)+0.2);
  var a=text(comp,s.eyebrow.toUpperCase(),FM,22,DIM,395,235,L_(),150); var b=text(comp,s.text,FB,46,PAPER,395,293,L_(),-20); reveal(a,t(c.in)+0.1,10,0.4); reveal(b,t(c.in)+0.14,10,0.4);
  hideAll([g,ic,tk,a,b],t(c.out)); }
// phone sits high and a little smaller so power captions (y ~1550-1730 in full zones) stay clear of it
var PH={cx:540,cy:880,w:580,h:1180};
function sc_phone(comp,s,t){ var T0=t(s.start), T1=t(s.end); fullBg(comp,T0,T1,s.hard_in,s.hard_out);
  var ft=importImg(s.image); var H=ft.height, W=ft.width; var mw=PH.w-60, mh=PH.h-60; var scale=mw/W*100;
  var ph=rect(comp,"phone",PH.cx,PH.cy,PH.w,PH.h,"#050B14",null,52); reveal(ph,T0+0.25,60,0.6);
  var scr=comp.layers.add(ft); scr.property("Transform").property("Scale").setValue([scale,scale]);
  var mask=rect(comp,"screenmask",PH.cx,PH.cy,mw,mh,"#FFFFFF",null,38); mask.moveBefore(scr);
  try { scr.setTrackMatte(mask, TrackMatteType.ALPHA); } catch(e) { scr.trackMatteType = TrackMatteType.ALPHA; }
  var p=scr.property("Transform").property("Position"); var y0=PH.cy+(H*scale/100)/2-mh/2-s.from*(scale/100), y1=y0-(s.to-s.from)*(scale/100);
  scr.property("Transform").property("Anchor Point").setValue([W/2,H/2]);
  p.setValueAtTime(T0+0.3,[PH.cx,y0]); p.setValueAtTime(T1-0.3,[PH.cx,y1]); easeAll(p,50);
  var o=scr.property("Transform").property("Opacity"); o.setValueAtTime(T0+0.2,0); o.setValueAtTime(T0+0.5,100);
  var sc2=ph.property("Transform").property("Scale"); sc2.setValueAtTime(T0+0.25,[100,100]); sc2.setValueAtTime(T1,[104,104]); easeAll(sc2,40);
  var lbl=text(comp,s.label||"learnevidence.com",FS,34,DIM,PH.cx,PH.cy+PH.h/2+80,null,20); reveal(lbl,T0+0.5,10,0.5); }
function build(S, OUT, FPS, AEP){
  app.beginSuppressDialogs(); app.newProject(); var rq=app.project.renderQueue;
  for(var i=0;i<S.length;i++){ var s=S[i]; var comp=app.project.items.addComp(s.id,1080,1920,1,s.end-s.start,FPS);
    var T0=s.start; var t=function(x){return x-T0;};
    var fn={title:sc_title,chips:sc_chips,mineral:sc_mineral,rxpad:sc_rxpad,split:sc_split,seal:sc_seal,price:sc_price,cta:sc_cta,badge:sc_badge,phone:sc_phone}[s.type];
    fn(comp,s,t);
    var item=rq.items.add(comp); var om=item.outputModule(1); om.applyTemplate("High Quality with Alpha"); om.file=new File(OUT+s.id+".mov"); }
  app.project.save(new File(OUT+(AEP||"graphics.aep"))); rq.render(); app.project.save(); app.endSuppressDialogs(false); }
