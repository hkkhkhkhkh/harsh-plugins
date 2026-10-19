// Motion kit for After Effects. gen_ae.py prepends `var OUT, G, ONLY, FPS, CW, CH, AEP, BRAND` and appends this file.
// Run it with osascript: tell application "Adobe After Effects 2026" to DoScriptFile "<job>/ae/graphics.jsx".
// One comp per graphic (1080x1920, alpha, ProRes 4444). g.type picks the template; every string and cue is data.
// Brand defaults below (Ink #10243D, Deep #1D3A57, Paper #F7F9FB, Dim #B9C9D8, Rule #CFD9E1, Red + Green = signal only);
// job.BRAND overrides any of them: {"ink","paper","dim","rule","red","green","deep","card","font_bold","font_semibold","font_medium"}.
// Motion system: things arrive fast and settle (ease out 75% influence), 0.40-0.52 s entries, 20 px rise,
// rows stagger by their own spoken cue, everything leaves together at cues.out in 0.28 s.
(function(){
function hex(h){return [parseInt(h.substr(1,2),16)/255, parseInt(h.substr(3,2),16)/255, parseInt(h.substr(5,2),16)/255];}
var INK="#10243D", PAPER="#F7F9FB", DIM="#B9C9D8", RULE="#CFD9E1", RED="#BE2A1B", GREEN="#10604F", DEEP="#1D3A57", CARD="#FFFFFF";
if (typeof BRAND != "undefined" && BRAND) { INK=BRAND.ink||INK; PAPER=BRAND.paper||PAPER; DIM=BRAND.dim||DIM; RULE=BRAND.rule||RULE; RED=BRAND.red||RED; GREEN=BRAND.green||GREEN; DEEP=BRAND.deep||DEEP; CARD=BRAND.card||CARD; }
var TONE={"refute":RED, "myth":RED, "support":GREEN, "true":GREEN, "neutral":DIM, "depends":DIM};
function ease(prop){ var n=prop.numKeys; for (var k=1;k<=n;k++){ var dims = (prop.value instanceof Array)? prop.value.length : 1;
  var ei=[], eo=[]; for (var d=0; d<dims; d++){ ei.push(new KeyframeEase(0,75)); eo.push(new KeyframeEase(0,75)); }
  try { prop.setTemporalEaseAtKey(k, ei, eo); } catch(e){} } }
function rect(comp, name, cx, cy, w, h, fill, stroke, r, sw){
  var L = comp.layers.addShape(); L.name = name;
  var g = L.property("Contents").addProperty("ADBE Vector Group");
  var rc = g.property("Contents").addProperty("ADBE Vector Shape - Rect");
  rc.property("Size").setValue([w,h]); rc.property("Roundness").setValue(r);
  if (stroke){ var s=g.property("Contents").addProperty("ADBE Vector Graphic - Stroke"); s.property("Color").setValue(hex(stroke)); s.property("Stroke Width").setValue(sw||2); }
  if (fill){ var f=g.property("Contents").addProperty("ADBE Vector Graphic - Fill"); f.property("Color").setValue(hex(fill)); }
  L.property("Transform").property("Position").setValue([cx,cy]);
  return L;
}
function line(comp, name, x1, y1, x2, y2, col, wdt){
  var L = comp.layers.addShape(); L.name = name;
  var g = L.property("Contents").addProperty("ADBE Vector Group");
  var p = g.property("Contents").addProperty("ADBE Vector Shape - Group");
  var s = new Shape(); s.vertices=[[x1,y1],[x2,y2]]; s.closed=false; p.property("Path").setValue(s);
  var st=g.property("Contents").addProperty("ADBE Vector Graphic - Stroke"); st.property("Color").setValue(hex(col)); st.property("Stroke Width").setValue(wdt);
  st.property("Line Cap").setValue(2);
  var tr = g.property("Contents").addProperty("ADBE Vector Filter - Trim");
  L.property("Transform").property("Position").setValue([0,0]); L.property("Transform").property("Anchor Point").setValue([0,0]);
  return tr;
}
function draw(trim, t0, d){ var e=trim.property("End"); e.setValueAtTime(0,0); e.setValueAtTime(Math.max(0,t0),0); e.setValueAtTime(Math.max(0,t0)+(d||0.3),100); ease(e); }
function text(comp, str, font, size, col, x, y, just, track){
  var L = comp.layers.addText(str); var tp = L.property("Source Text"); var d = tp.value;
  d.resetCharStyle(); d.font = font; d.fontSize = size; d.fillColor = hex(col); d.applyFill = true; d.applyStroke=false;
  d.justification = just || ParagraphJustification.CENTER_JUSTIFY; if (track) d.tracking = track;
  tp.setValue(d);
  L.property("Transform").property("Position").setValue([x,y]);
  return L;
}
function boxtext(comp, str, font, size, col, x, y, w, h, just, lead){
  var L = comp.layers.addBoxText([w,h], str); var tp = L.property("Source Text"); var d = tp.value;
  d.resetCharStyle(); d.font = font; d.fontSize = size; d.fillColor = hex(col); d.applyFill = true; d.applyStroke=false;
  d.justification = just || ParagraphJustification.LEFT_JUSTIFY; if (lead) { d.autoLeading=false; d.leading = lead; }
  tp.setValue(d);
  // anchor on the text itself: centre for centred text, left-middle for left text, so (x, y) is where it visibly sits
  var r = L.sourceRectAtTime(0, false), cen = (d.justification == ParagraphJustification.CENTER_JUSTIFY);
  L.property("Transform").property("Anchor Point").setValue([cen ? r.left + r.width/2 : r.left, r.top + r.height/2]);
  L.property("Transform").property("Position").setValue([x,y]);
  return L;
}
function reveal(L, t, rise, dur){ // fade + rise in at t (seconds, comp time)
  var o=L.property("Transform").property("Opacity"), p=L.property("Transform").property("Position");
  var v=p.value; dur = dur || 0.52; rise = (rise===undefined)?20:rise;
  o.setValueAtTime(Math.max(0,t-0.001-1/FPS),0); o.setValueAtTime(t,0); o.setValueAtTime(t+dur*0.7,100);
  p.setValueAtTime(t,[v[0],v[1]+rise]); p.setValueAtTime(t+dur,[v[0],v[1]]); ease(p); ease(o);
}
function hide(L, t, dur){ var o=L.property("Transform").property("Opacity"); dur=dur||0.28;
  var cur = o.numKeys ? o.valueAtTime(t,false) : 100; o.setValueAtTime(t,cur); o.setValueAtTime(t+dur,0); }
function hideAll(ls, t){ for (var k=0;k<ls.length;k++) hide(ls[k], t); }
function growX(L, t, d, anchorLeftX, w){ // bar grows from its left edge
  var tr=L.property("Transform"); tr.property("Anchor Point").setValue([-w/2,0]);
  var p=tr.property("Position").value; tr.property("Position").setValue([anchorLeftX, p[1]]);
  var s=tr.property("Scale"); s.setValueAtTime(0,[0,100]); s.setValueAtTime(Math.max(0,t),[0,100]); s.setValueAtTime(Math.max(0,t)+(d||0.6),[100,100]); ease(s);
}
var FB="ArchivoEF-Bold", FS="ArchivoEF-SemiBold", FM="ArchivoEF-Medium";   // font PostScript names; must be installed for AE
if (typeof BRAND != "undefined" && BRAND) { FB=BRAND.font_bold||FB; FS=BRAND.font_semibold||FS; FM=BRAND.font_medium||FM; }

// ---------------------------------------------------------------- templates
var T = {};
T.chips_strike = function(comp, g, c, t){ // three chips appear on their words, get struck through, swap to one card
  var labels=[], gap=26, total=0;
  for (var k=0;k<g.labels.length;k++) labels.push([g.labels[k][0], c[g.labels[k][1]], g.labels[k][2]]);
  for (var k=0;k<labels.length;k++) total+=labels[k][2]; total+=gap*(labels.length-1); var x=540-total/2;
  var chips=[], Y=g.y||320;
  for (var k=0;k<labels.length;k++){ var w=labels[k][2], cx=x+w/2;
    var R=rect(comp,"chip"+k,cx,Y,w,104,CARD,RULE,10);
    var TX=text(comp,labels[k][0],FS,46,INK,cx,Y+16);
    var trim=line(comp,"strike"+k,cx-w/2+14,Y+1,cx+w/2-14,Y+1,RED,6);
    trim.property("End").setValueAtTime(0,0); trim.property("End").setValueAtTime(t(c.strike)+k*0.08,0); trim.property("End").setValueAtTime(t(c.strike)+k*0.08+0.28,100);
    reveal(R,t(labels[k][1])); reveal(TX,t(labels[k][1]));
    chips.push(R,TX,comp.layer("strike"+k)); x+=w+gap; }
  hideAll(chips, t(c.one)-0.1);
  var card=rect(comp,"one",540,Y+10,900,160,INK,null,14);
  var eb=text(comp,g.eyebrow,FM,28,DIM,540,Y-23,null,150);
  var tt=text(comp,g.title,FB,56,PAPER,540,Y+49);
  reveal(card,t(c.one)+0.05); reveal(eb,t(c.one)+0.1); reveal(tt,t(c.one)+0.14);
  hideAll([card,eb,tt], t(c.out));
};
T.list = function(comp, g, c, t){ // eyebrow + rows that land on their spoken words
  var rows=g.rows, n=rows.length, rowH=(n>3?62:72), h=70+n*rowH+26, top=g.top||170, cy=top+h/2;
  var card=rect(comp,"card",540,cy,900,h,INK,null,14); reveal(card,t(c.card),16);
  var eb=text(comp,g.head,FM,28,DIM,150,top+54,ParagraphJustification.LEFT_JUSTIFY,150); reveal(eb,t(c.card)+0.06,16);
  var all=[card,eb];
  for (var k=0;k<n;k++){ var y=top+70+k*rowH+rowH*0.68;
    var dv=line(comp,"div"+k,150,y-rowH*0.68,930,y-rowH*0.68,DEEP,2); dv.property("End").setValue(100);
    var mark=text(comp,"+",FB,50,DIM,168,y,ParagraphJustification.CENTER_JUSTIFY);
    var L=text(comp,rows[k][0],FS,(n>3?48:52),PAPER,212,y,ParagraphJustification.LEFT_JUSTIFY);
    var rc=c[rows[k][1]];
    reveal(mark,t(rc),14,0.4); reveal(L,t(rc),14,0.4); reveal(comp.layer("div"+k),t(rc),0,0.3);
    all.push(mark,L,comp.layer("div"+k)); }
  hideAll(all, t(c.out));
};
T.price = function(comp, g, c, t){ // old price struck, real price lands, refund chip
  var X=g.x||800;
  var card=rect(comp,"card",X,335,480,330,INK,null,14); reveal(card,t(c.card),16);
  var lk=text(comp,g.old,FS,36,DIM,X,230); reveal(lk,t(c.card)+0.05,16);
  var st=line(comp,"lstrike",X-135,217,X+135,217,RED,5);
  st.property("End").setValueAtTime(0,0); st.property("End").setValueAtTime(t(c.card)+0.35,0); st.property("End").setValueAtTime(t(c.card)+0.65,100);
  var pr=text(comp,g.price,FB,104,PAPER,X,345); reveal(pr,t(c.price),18);
  var yr=text(comp,g.unit,FM,30,DIM,X,390); reveal(yr,t(c.price)+0.1,14);
  var all=[card,lk,comp.layer("lstrike"),pr,yr];
  if (g.chip){ var chip=rect(comp,"chip",X,448,420,58,PAPER,null,6); var ct=text(comp,g.chip,FS,30,INK,X,459);
    reveal(chip,t(c.refund),10,0.4); reveal(ct,t(c.refund),10,0.4); all.push(chip,ct); }   // chip only when a refund is spoken
  hideAll(all, t(c.out));
};
T.cta = function(comp, g, c, t){ // button between chin and captions, arrow nudges
  var Y=g.y||1128, BX=g.x||540, BW=g.w||780;
  var btn=rect(comp,"btn",BX,Y,BW,112,INK,null,8); var bt=text(comp,g.text,FS,54,PAPER,BX-35,Y+18);
  var ar=text(comp,"↓",FB,54,PAPER,BX+BW/2-60,Y+18);
  reveal(btn,t(c.btn),22); reveal(bt,t(c.btn)+0.04,22); reveal(ar,t(c.btn)+0.08,22);
  var p=ar.property("Transform").property("Position"); var v=[BX+BW/2-60,Y+18];
  for (var k=0;k<3;k++){ var tt=t(c.btn)+0.6+k*0.5; p.setValueAtTime(tt,v); p.setValueAtTime(tt+0.25,[v[0],v[1]+10]); p.setValueAtTime(tt+0.5,v); }
};
T.study = function(comp, g, c, t){ // journal / year eyebrow, the finding, n + design chips, finding underline on c.hl
  var top=g.top||170, h=300, cy=top+h/2, col=TONE[g.tone||"neutral"];
  var card=rect(comp,"card",540,cy,900,h,INK,null,14); reveal(card,t(c.card),16);
  var eb=text(comp,(g.journal+"  ·  "+g.year).toUpperCase(),FM,26,DIM,130,top+56,ParagraphJustification.LEFT_JUSTIFY,120); reveal(eb,t(c.card)+0.06,16);
  var fd=boxtext(comp,g.finding,FB,46,PAPER,130,top+140,800,120,ParagraphJustification.LEFT_JUSTIFY,54); reveal(fd,t(c.card)+0.1,16);
  var ul=line(comp,"hl",130,top+214,130+Math.min(800,g.hl_width||520),top+214,col,6); draw(ul,t(c.hl||c.card+0.6),0.35);
  var all=[card,eb,fd,comp.layer("hl")], x=130;
  var chips=[g.n?("n = "+g.n):null, g.design||null];
  for (var k=0;k<chips.length;k++){ if(!chips[k]) continue; var w=chips[k].length*15+44;
    var R=rect(comp,"chip"+k,x+w/2,top+256,w,46,null,DIM,6,2); var TX=text(comp,chips[k],FM,24,DIM,x+w/2,top+265);
    reveal(R,t(c.card)+0.18+k*0.06,10,0.4); reveal(TX,t(c.card)+0.18+k*0.06,10,0.4); all.push(R,TX); x+=w+16; }
  hideAll(all, t(c.out));
};
T.verdict = function(comp, g, c, t){ // MYTH / TRUE / IT DEPENDS stamp: scale 140% -> 96% -> 100%, slight tilt
  var col=TONE[g.tone||(g.word=="TRUE"?"true":(g.word=="MYTH"?"myth":"depends"))], X=g.x||540, Y=g.y||330;
  var w=g.word.length*52+120;
  var box=rect(comp,"stamp",0,0,w,150,null,col,12,8); var tx=text(comp,g.word,FB,96,col,0,34,null,40);
  var nl=comp.layers.addNull(); nl.property("Transform").property("Position").setValue([X,Y]);
  box.parent=nl; tx.parent=nl; box.property("Transform").property("Position").setValue([0,0]); tx.property("Transform").property("Position").setValue([0,34]);
  var s=nl.property("Transform").property("Scale"), r=nl.property("Transform").property("Rotation"), T0=t(c.stamp);
  s.setValueAtTime(T0,[140,140]); s.setValueAtTime(T0+0.16,[96,96]); s.setValueAtTime(T0+0.3,[100,100]); ease(s);
  r.setValue(g.tilt===undefined?-6:g.tilt);
  var all=[box,tx];
  for (var k=0;k<all.length;k++){ var o=all[k].property("Transform").property("Opacity"); o.setValueAtTime(Math.max(0,T0-1/FPS),0); o.setValueAtTime(T0,100); }
  if (g.sub){ var sb=text(comp,g.sub,FS,40,PAPER,X,Y+130); reveal(sb,T0+0.25,12,0.4); all.push(sb); }
  hideAll(all, t(c.out));
};
T.stat = function(comp, g, c, t){ // number counts up and settles on c.land, label + source under it
  var X=g.x||540, top=g.top||170, h=g.source?320:280, cy=top+h/2;
  var card=rect(comp,"card",X,cy,g.w||620,h,INK,null,14); reveal(card,t(c.card),16);
  var num=text(comp,(g.prefix||"")+"0"+(g.suffix||""),FB,g.size||140,PAPER,X,top+160); reveal(num,t(c.card)+0.04,16);
  var t0=t(c.card)+0.1, t1=t(c.land);
  num.property("Source Text").expression =
    "var v=ease(time,"+t0+","+t1+",0,"+g.value+");var s=v.toFixed("+(g.decimals||0)+").split('.');" +
    "s[0]=s[0].replace(/\\B(?=(\\d{3})+(?!\\d))/g,',');'"+(g.prefix||"")+"'+s.join('.')+'"+(g.suffix||"")+"'";
  var lb=text(comp,g.label,FS,38,DIM,X,top+225); reveal(lb,t(c.card)+0.12,14);
  var all=[card,num,lb];
  if (g.source){ var sc=text(comp,g.source,FM,24,DIM,X,top+280,null,40); reveal(sc,t(c.card)+0.2,10,0.4); all.push(sc); }
  hideAll(all, t(c.out));
};
T.compare = function(comp, g, c, t){ // labelled bars growing to their values on their cues
  var rows=g.rows, n=rows.length, rowH=110, top=g.top||170, h=90+n*rowH, cy=top+h/2, max=0;
  for (var k=0;k<n;k++) max=Math.max(max, rows[k][1]);
  var card=rect(comp,"card",540,cy,900,h,INK,null,14); reveal(card,t(c.card),16);
  var all=[card];
  if (g.head){ var eb=text(comp,g.head,FM,28,DIM,130,top+56,ParagraphJustification.LEFT_JUSTIFY,150); reveal(eb,t(c.card)+0.06,16); all.push(eb); }
  var BX=130, BW=640;
  for (var k=0;k<n;k++){ var y=top+100+k*rowH, rc=c[rows[k][3]||"card"], w=Math.max(8,BW*rows[k][1]/max);
    var lb=text(comp,rows[k][0],FS,36,PAPER,BX,y,ParagraphJustification.LEFT_JUSTIFY); reveal(lb,t(rc),10,0.4);
    var tr=rect(comp,"track"+k,BX+BW/2,y+36,BW,22,DEEP,null,6); reveal(tr,t(rc),0,0.3);
    var bar=rect(comp,"bar"+k,BX+w/2,y+36,w,22,(rows[k][4]&&TONE[rows[k][4]])||PAPER,null,6); growX(bar,t(rc)+0.05,0.6,BX,w);
    var vl=text(comp,rows[k][2],FB,36,PAPER,BX+BW+20,y+48,ParagraphJustification.LEFT_JUSTIFY); reveal(vl,t(rc)+0.5,8,0.35);
    all.push(lb,tr,bar,vl); }
  hideAll(all, t(c.out));
};
T.steps = function(comp, g, c, t){ // mechanism chain: nodes + arrows build one by one (vertical if > 3)
  var st=g.steps, n=st.length, top=g.top||170, all=[];
  if (n<=3){
    var w=260, gap=60, x0=540-(n*w+(n-1)*gap)/2, y=top+90;
    for (var k=0;k<n;k++){ var cx=x0+w/2+k*(w+gap), rc=c[st[k][1]];
      var R=rect(comp,"node"+k,cx,y,w,140,INK,null,14); var L=boxtext(comp,st[k][0],FS,36,PAPER,cx,y,w-30,110,ParagraphJustification.CENTER_JUSTIFY,40);
      reveal(R,t(rc),16); reveal(L,t(rc)+0.04,16); all.push(R,L);
      if (k>0){ var a=line(comp,"arrow"+k,cx-w/2-gap+8,y,cx-w/2-8,y,INK,6); draw(a,t(rc)-0.12,0.2); all.push(comp.layer("arrow"+k)); } }
  } else {
    var h=92, gap=34;
    for (var k=0;k<n;k++){ var y=top+h/2+k*(h+gap), rc=c[st[k][1]];
      var R=rect(comp,"node"+k,540,y,760,h,INK,null,12); var L=text(comp,st[k][0],FS,40,PAPER,540,y+14);
      reveal(R,t(rc),14,0.4); reveal(L,t(rc)+0.04,14,0.4); all.push(R,L);
      if (k>0){ var a=line(comp,"arrow"+k,540,y-h/2-gap+4,540,y-h/2-4,INK,6); draw(a,t(rc)-0.12,0.2); all.push(comp.layer("arrow"+k)); } }
  }
  hideAll(all, t(c.out));
};
T.paper = function(comp, g, c, t){ // real paper screenshot in a white card, slow drift, highlighter wipes over g.hl
  var W=g.w||880, top=g.top||170;
  var foot=app.project.importFile(new ImportOptions(new File(g.image)));
  var sc=W/foot.width*100, H=foot.height*sc/100;
  var card=rect(comp,"card",540,top+H/2,W+28,H+28,CARD,null,14); reveal(card,t(c.card),16);
  var img=comp.layers.add(foot); img.property("Transform").property("Scale").setValue([sc,sc]);
  img.property("Transform").property("Position").setValue([540,top+H/2]); reveal(img,t(c.card)+0.04,16);
  var all=[card,img];
  if (g.hl){ var hx=540-W/2+g.hl[0]*sc/100, hy=top+g.hl[1]*sc/100, hw=g.hl[2]*sc/100, hh=g.hl[3]*sc/100;
    var hl=rect(comp,"hl",hx+hw/2,hy+hh/2,hw,hh,TONE[g.tone||"support"],null,4); hl.property("Transform").property("Opacity").setValue(32);
    growX(hl,t(c.hl),0.5,hx,hw); all.push(hl); }
  var drift=g.drift===undefined?18:g.drift;
  for (var k=0;k<all.length;k++){ var p=all[k].property("Transform").property("Position"), v=p.valueAtTime(t(c.card)+0.6,false);
    p.setValueAtTime(t(c.out),[v[0],v[1]-drift]); }
  hideAll(all, t(c.out));
};

T.bigword = function(comp, g, c, t){ // kinetic type: stacked lines [text, size, tone|"dim", cue], centred on g.y
  var L=g.lines, y=g.y||760, gap=g.gap||22, tot=0, all=[], BX=g.x||540;
  for (var k=0;k<L.length;k++) tot += (L[k][1]||120);
  tot += gap*(L.length-1); var yy = y - tot/2;
  if (g.panel){ var pn=rect(comp,"panel",BX,y+tot*0.08,g.panel,tot+90,INK,null,14); reveal(pn,t(c.card),16); all.push(pn); }
  for (var k=0;k<L.length;k++){ var sz=L[k][1]||120, tone=L[k][2];
    var col = tone=="dim" ? DIM : (TONE[tone] && tone!="neutral" ? TONE[tone] : PAPER);
    var tl=text(comp,L[k][0],(sz>=90?FB:FS),sz,col,BX,yy+sz*0.8,null,(sz>=90?-10:0));
    var cue = L[k][3] ? c[L[k][3]] : c.card + k*0.08;
    reveal(tl,t(cue),30,0.45); all.push(tl); yy += sz+gap; }
  hideAll(all, t(c.out));
};
T.wordmark = function(comp, g, c, t){ // Evidence First wordmark (ef-brand): "First" reversed out of a Paper block
  var y=g.y||700, sz=g.size||150;
  var a=text(comp,"Evidence",FB,sz,PAPER,540,y,null,-40);
  var b=text(comp,"First",FB,sz,INK,540,y+sz*0.95,null,-40);
  var r=b.sourceRectAtTime(0,false), p=b.property("Transform").property("Position").value;
  var blk=rect(comp,"blk",p[0]+r.left+r.width/2,p[1]+r.top+r.height/2,r.width+sz*0.16,r.height+sz*0.1,PAPER,null,0); blk.moveAfter(b);
  reveal(a,t(c.card),24,0.45); reveal(blk,t(c.card)+0.1,24,0.45); reveal(b,t(c.card)+0.1,24,0.45);
  hideAll([a,blk,b], t(c.out));
};

function rrShape(x0, y0, w, h, r){ // rounded-rect mask path in layer px
  var k=0.5523*r, s=new Shape();
  s.vertices=[[x0+r,y0],[x0+w-r,y0],[x0+w,y0+r],[x0+w,y0+h-r],[x0+w-r,y0+h],[x0+r,y0+h],[x0,y0+h-r],[x0,y0+r]];
  s.inTangents=[[-k,0],[0,0],[0,-k],[0,0],[k,0],[0,0],[0,k],[0,0]];
  s.outTangents=[[0,0],[k,0],[0,0],[0,k],[0,0],[-k,0],[0,0],[0,-k]];
  s.closed=true; return s; }
T.wall = function(comp, g, c, t){ // video wall: real student clips (muted) pop into a grid one by one, name chip on each
  var cols=g.cols||3, S=g.tile||300, gap=g.gap||20, n=g.tiles.length, rows=Math.ceil(n/cols);
  var W=cols*S+(cols-1)*gap, H=rows*S+(rows-1)*gap, x0=CW/2-W/2, y0=(g.top||(CH/2-H/2)), all=[];
  if (g.head){ var eb=text(comp,g.head,FM,30,DIM,CW/2,y0-38,null,150); reveal(eb,t(c.card),14); all.push(eb); }
  for (var k=0;k<n;k++){ var tl=g.tiles[k], col=k%cols, row=Math.floor(k/cols);
    var cx=x0+S/2+col*(S+gap), cy=y0+S/2+row*(S+gap), T0=t(c["t"+k]);
    var foot=app.project.importFile(new ImportOptions(new File(tl.file)));
    var L=comp.layers.add(foot); L.audioEnabled=false; var zoom=tl.zoom||1.25;
    L.startTime=Math.max(0,T0)-(tl.lead||0);   // BEFORE any keyframe: keys live in layer time and move with startTime
    var sc=S*zoom/foot.width*100, crop=foot.width/zoom;                    // show a (1080/zoom)-px square round the face
    var fx=Math.min(Math.max(crop/2,tl.fx),foot.width-crop/2), fy=Math.min(Math.max(crop/2,tl.fy),foot.height-crop/2);
    var mk=L.property("Masks").addProperty("Mask"); mk.property("Mask Path").setValue(rrShape(fx-crop/2,fy-crop/2,crop,crop,16*100/sc));
    L.property("Transform").property("Anchor Point").setValue([fx,fy]);
    L.property("Transform").property("Position").setValue([cx,cy]);
    var s=L.property("Transform").property("Scale"); s.setValueAtTime(Math.max(0,T0),[sc*0.6,sc*0.6]); s.setValueAtTime(T0+0.22,[sc*1.04,sc*1.04]); s.setValueAtTime(T0+0.34,[sc,sc]); ease(s);
    var o=L.property("Transform").property("Opacity"); o.setValueAtTime(Math.max(0,T0-1/FPS),0); o.setValueAtTime(T0,100);
    all.push(L);
    if (tl.name){ var w=tl.name.length*19+40, ny=cy+S/2-34;
      var R=rect(comp,"nm"+k,cx-S/2+18+w/2,ny,w,44,PAPER,null,8); var TX=text(comp,tl.name,FS,26,INK,cx-S/2+18+w/2,ny+9);
      reveal(R,T0+0.2,8,0.3); reveal(TX,T0+0.2,8,0.3); all.push(R,TX); }
  }
  hideAll(all, t(c.out));
};
T.side = function(comp, g, c, t){ // right-side stack for a face that sits left (captions own y 1280): eyebrow chip + short rows
  // rows [[text, cue, mode]] mode: "plus" (default) | "x" (red cross, a 'don't') | "strike" (struck through at c.strike)
  // optional g.final {title, sub} swaps the rows for one Paper card at c.final
  var W=g.w||440, X=g.x||(1040-W/2), y=g.top||210, L0=X-W/2, all=[], rowsL=[];
  if (g.head){ var hw=g.head.length*17+44; var hc=rect(comp,"headchip",L0+hw/2,y,hw,50,PAPER,null,8);
    var ht=text(comp,g.head,FS,26,INK,L0+hw/2,y+9,null,60); reveal(hc,t(c.card),14,0.4); reveal(ht,t(c.card)+0.04,14,0.4); rowsL.push(hc,ht); y+=50; }
  for (var k=0;k<g.rows.length;k++){ var r=g.rows[k], mode=r[2]||"plus", rc=c[r[1]], h=92, cy=y+14+h/2;
    var R=rect(comp,"row"+k,X,cy,W,h,INK,null,10);
    var acc=rect(comp,"acc"+k,L0+5,cy,10,h,(mode=="x"?RED:(g.accent?TONE[g.accent]:DIM)),null,0);
    var mk=text(comp,(mode=="x"?"✕":"+"),FB,(mode=="x"?34:46),(mode=="x"?RED:DIM),L0+44,cy+(mode=="x"?12:16));
    var tx=text(comp,r[0],FS,(r[0].length>18?33:37),PAPER,L0+76,cy+13,ParagraphJustification.LEFT_JUSTIFY);
    reveal(R,t(rc),18,0.42); reveal(acc,t(rc),18,0.42); reveal(mk,t(rc)+0.03,18,0.42); reveal(tx,t(rc)+0.05,18,0.42);
    rowsL.push(R,acc,mk,tx);
    if (mode=="strike"){ var tw=tx.sourceRectAtTime(0,false).width;
      var st=line(comp,"strike"+k,L0+70,cy,L0+82+tw,cy,RED,6); var ts=t(c.strike)+k*0.08;
      st.property("End").setValueAtTime(0,0); st.property("End").setValueAtTime(ts,0); st.property("End").setValueAtTime(ts+0.26,100);
      var o=tx.property("Transform").property("Opacity"); o.setValueAtTime(ts+0.2,100); o.setValueAtTime(ts+0.4,55); rowsL.push(comp.layer("strike"+k)); }
    y+=h+14; }
  if (g.final){ hideAll(rowsL, t(c.final)-0.1);
    var fy=(g.top||210)+120, fc=rect(comp,"final",X,fy,W,220,PAPER,null,14);
    var ft=boxtext(comp,g.final.title,FB,54,INK,X,fy-(g.final.sub?26:0),W-60,140,ParagraphJustification.CENTER_JUSTIFY,58);
    reveal(fc,t(c.final),20); reveal(ft,t(c.final)+0.05,20); all.push(fc,ft);
    if (g.final.sub){ var fs=text(comp,g.final.sub,FM,28,DEEP,X,fy+70); reveal(fs,t(c.final)+0.1,16); all.push(fs); }
  } else all=all.concat(rowsL);
  hideAll(all, t(c.out));
};
// ---- split scene (the approved 9:16 split layout): Ink plate with a rounded 560 px window at y 70-630 where the
// A-roll shows through (Resolve moves his face into it), panel content in y 680-1280, captions drop to y 1420.
var WIN={w:560,h:560,y:70};
function splitPlate(comp,t0,t1,hardIn,hardOut){ var L=comp.layers.addShape(); L.name="plate"; var root=L.property("Contents");
  var g=root.addProperty("ADBE Vector Group"); var cc=g.property("Contents");
  var outer=cc.addProperty("ADBE Vector Shape - Rect"); outer.property("Size").setValue([1080,1920]); outer.property("Position").setValue([540,960]);
  cc.addProperty("ADBE Vector Shape - Rect");
  var mp=cc.addProperty("ADBE Vector Filter - Merge"); mp.property("Mode").setValue(3);   // subtract: the hole is the window
  var f=cc.addProperty("ADBE Vector Graphic - Fill"); f.property("Color").setValue(hex(INK));
  var hole=L.property("Contents").property(1).property("Contents").property(2); var hs=hole.property("Size"), hp=hole.property("Position"), hr=hole.property("Roundness");
  L.property("Transform").property("Anchor Point").setValue([0,0]); L.property("Transform").property("Position").setValue([0,0]);
  var ti=hardIn?t0:t0+0.55, to=hardOut?t1:t1-0.5;
  if(!hardIn){ hs.setValueAtTime(t0,[1080,1920]); hp.setValueAtTime(t0,[540,960]); hr.setValueAtTime(t0,0); }
  hs.setValueAtTime(ti,[WIN.w,WIN.h]); hp.setValueAtTime(ti,[540,WIN.y+WIN.h/2]); hr.setValueAtTime(ti,28);
  hs.setValueAtTime(to,[WIN.w,WIN.h]); hp.setValueAtTime(to,[540,WIN.y+WIN.h/2]); hr.setValueAtTime(to,28);
  if(!hardOut){ hs.setValueAtTime(t1,[1080,1920]); hp.setValueAtTime(t1,[540,960]); hr.setValueAtTime(t1,0); }
  ease(hs); ease(hp); ease(hr);
  var border=rect(comp,"winborder",540,WIN.y+WIN.h/2,WIN.w,WIN.h,null,"#2E4A66",28,2);
  var bo=border.property("Transform").property("Opacity"); bo.setValueAtTime(0,hardIn?100:0); if(!hardIn){ bo.setValueAtTime(ti-0.05,0); bo.setValueAtTime(ti+0.15,100); }
  if(!hardOut){ bo.setValueAtTime(to-0.05,100); bo.setValueAtTime(to+0.05,0); }
  return L; }
function wrap2(txt){ if(txt.length<=18) return txt; var m=Math.floor(txt.length/2), best=-1; for(var i=0;i<txt.length;i++){ if(txt.charAt(i)==" " && (best<0 || Math.abs(i-m)<Math.abs(best-m))) best=i; } return best<0?txt:txt.substr(0,best)+"\r"+txt.substr(best+1); }
T.split = function(comp, g, c, t){ // rows [[text, cue, mode]] mode plus|check|x|strike; g.final {title, sub} swaps the rows at c.final
  var T0=t(g.start), T1=t(g.end); splitPlate(comp,T0,T1,g.hard_in,g.hard_out);
  var tin=T0+(g.hard_in?0.05:0.45), content=[];
  var eb=line(comp,"ebline",90,697,136,697,RED,4); draw(eb,tin,0.3);
  var et=text(comp,g.head,FM,28,DIM,152,706,ParagraphJustification.LEFT_JUSTIFY,150); reveal(et,tin+0.05,10,0.4); content.push(comp.layer("ebline"),et);
  var n=g.rows.length, gap=(n>4?100:112), y0=800;
  for (var j=0;j<n;j++){ var r=g.rows[j], mode=r[2]||"plus", rc=Math.max(tin+0.1,t(c[r[1]])), y=y0+j*gap;
    var dv=line(comp,"dv"+j,90,y-gap/2+4,990,y-gap/2+4,DEEP,2); draw(dv,rc,0.3); content.push(comp.layer("dv"+j));
    var mk=null;
    if (mode=="x") mk=text(comp,"✕",FB,40,RED,112,y+14);
    else mk=text(comp,"+",FB,54,DIM,112,y+18);
    if (mk){ reveal(mk,rc,14,0.4); content.push(mk); }
    var tx=text(comp,r[0],FB,(r[0].length>22?44:52),PAPER,152,y+18,ParagraphJustification.LEFT_JUSTIFY,-20); reveal(tx,rc+0.03,14,0.4); content.push(tx);
    if (mode=="strike"){ var tw=tx.sourceRectAtTime(0,false).width, ts=t(c.strike)+j*0.08;
      var st=line(comp,"strike"+j,146,y,160+tw,y,RED,7); st.property("End").setValueAtTime(0,0); st.property("End").setValueAtTime(ts,0); st.property("End").setValueAtTime(ts+0.28,100);
      var o=tx.property("Transform").property("Opacity"); o.setValueAtTime(ts+0.2,100); o.setValueAtTime(ts+0.45,45); content.push(comp.layer("strike"+j)); }
  }
  var out=t(c.out);   // panel content always leaves; only the plate carries across a hard_out join
  if (g.final){ var tf=t(c.final); for (var k=0;k<content.length;k++) if (content[k]!==et && content[k]!==comp.layer("ebline")) hide(content[k],tf-0.12,0.2);
    var ft=text(comp,wrap2(g.final.title),FB,78,PAPER,540,910,null,-30); reveal(ft,tf,22,0.5);
    var fs=g.final.sub?text(comp,g.final.sub,FM,34,DIM,540,1130):null; if(fs) reveal(fs,tf+0.12,14,0.45);
    hide(ft,out); if(fs) hide(fs,out); hide(et,out); hide(comp.layer("ebline"),out);
  } else hideAll(content,out);
};
T.name = function(comp, g, c, t){ // name tag for testimonial clips without one burned in: Paper chip, name + role
  var X=g.x||70, Y=g.y||1530, w=Math.max(g.name.length*27, g.role.length*15)+64;
  var R=rect(comp,"tag",X+w/2,Y,w,112,PAPER,null,10);
  var bar=rect(comp,"bar",X+6,Y,12,112,INK,null,0);
  var nm=text(comp,g.name,FB,44,INK,X+34,Y-4,ParagraphJustification.LEFT_JUSTIFY);
  var rl=text(comp,g.role,FM,26,DEEP,X+34,Y+36,ParagraphJustification.LEFT_JUSTIFY);
  reveal(R,t(c.card),16); reveal(bar,t(c.card),16); reveal(nm,t(c.card)+0.06,16); reveal(rl,t(c.card)+0.1,16);
  hideAll([R,bar,nm,rl], t(c.out));
};

// ---------------------------------------------------------------- 16:9 VSL templates
// Layout: he sits centre-frame; a right-hand Ink plate (x 1100-1920) slides in while Resolve slides him left (zones.json "side"),
// or an opaque full-frame scene (g.full). Arrows, ticks and crosses are drawn shapes, never glyphs.
var PX0=1100, CX0=1180, CXW=660;
function pathL(comp, name, pts, col, wdt, closed){
  var L = comp.layers.addShape(); L.name = name;
  var g = L.property("Contents").addProperty("ADBE Vector Group");
  var p = g.property("Contents").addProperty("ADBE Vector Shape - Group");
  var s = new Shape(); s.vertices = pts; s.closed = !!closed; p.property("Path").setValue(s);
  var st = g.property("Contents").addProperty("ADBE Vector Graphic - Stroke"); st.property("Color").setValue(hex(col)); st.property("Stroke Width").setValue(wdt);
  st.property("Line Cap").setValue(2); st.property("Line Join").setValue(2);
  L.property("Transform").property("Anchor Point").setValue([0,0]); L.property("Transform").property("Position").setValue([0,0]);
  return L;
}
function markChip(comp, name, kind, x, y, s){ // filled square chip with a drawn glyph; returns [layers]
  s = s || 40; var col = {"check":GREEN, "down":GREEN, "upgood":GREEN, "x":RED, "up":RED, "plus":DEEP, "dot":DEEP}[kind] || DEEP, h = s/2, q = s*0.26; if (kind=="upgood") kind = "up";
  var R = rect(comp, name+"_bg", x, y, s, s, col, null, 6), G2;
  if (kind=="check") G2 = pathL(comp, name+"_g", [[x-q,y+1],[x-q*0.25,y+q*0.8],[x+q,y-q*0.7]], PAPER, 5);
  else if (kind=="x") { G2 = pathL(comp, name+"_g", [[x-q*0.8,y-q*0.8],[x+q*0.8,y+q*0.8]], PAPER, 5); var g3 = pathL(comp, name+"_g2", [[x+q*0.8,y-q*0.8],[x-q*0.8,y+q*0.8]], PAPER, 5); return [R,G2,g3]; }
  else if (kind=="down") G2 = pathL(comp, name+"_g", [[x-q*0.8,y],[x,y+q],[x+q*0.8,y],[x,y+q],[x,y-q]], PAPER, 5);
  else if (kind=="up") G2 = pathL(comp, name+"_g", [[x-q*0.8,y],[x,y-q],[x+q*0.8,y],[x,y-q],[x,y+q]], PAPER, 5);
  else if (kind=="plus") { G2 = pathL(comp, name+"_g", [[x-q,y],[x+q,y]], PAPER, 5); var g4 = pathL(comp, name+"_g2", [[x,y-q],[x,y+q]], PAPER, 5); return [R,G2,g4]; }
  else G2 = pathL(comp, name+"_g", [[x-2,y],[x+2,y]], PAPER, 8);
  return [R,G2];
}
function arrowR(comp, name, x1, x2, y, col, w){ return pathL(comp, name, [[x1,y],[x2,y],[x2-16,y-14],[x2,y],[x2-16,y+14]], col||DIM, w||6); }
function revealAll(ls, t, rise, dur){ for (var i=0;i<ls.length;i++) reveal(ls[i], t+0.02*i, rise, dur); }
function textW(L){ return L.sourceRectAtTime(0,false).width; }
function plate(comp, g, T0, T1){ // right-hand Ink plate: slides in from the right over 0.45 s, out over 0.40 s (none on hard joins)
  var w = 1920-PX0, P = rect(comp, "plate", PX0+w/2, 540, w, 1080, INK, null, 0), p = P.property("Transform").property("Position");
  var edge = rect(comp, "plate_edge", PX0+1, 540, 2, 1080, DEEP, null, 0), pe = edge.property("Transform").property("Position");
  if (!g.hard_in){ p.setValueAtTime(T0,[PX0+w/2+w,540]); p.setValueAtTime(T0+0.45,[PX0+w/2,540]); pe.setValueAtTime(T0,[PX0+1+w,540]); pe.setValueAtTime(T0+0.45,[PX0+1,540]); }
  if (!g.hard_out){ p.setValueAtTime(T1-0.40,[PX0+w/2,540]); p.setValueAtTime(T1,[PX0+w/2+w,540]); pe.setValueAtTime(T1-0.40,[PX0+1,540]); pe.setValueAtTime(T1,[PX0+1+w,540]); }
  ease(p); ease(pe);
  return g.hard_in ? T0+0.05 : T0+0.45;
}
// blocks: [{k:"eyebrow", text}, {k:"big", text | from/to, cue, size}, {k:"sub", text, cue}, {k:"row", text, mark, cue},
//          {k:"chips", items:[[text, cue]]}, {k:"source", text}]; g.final {title, sub} swaps everything below the eyebrow at c.final
function quoteLines(b, cw){ return Math.max(1, Math.ceil(b.text.length * 15.5 / (cw - 90))); }
function blockH(b, cw){ if (b.k=="photos") return (b.h||340) + 50; if (b.k=="quote") return 52 + quoteLines(b, cw||660)*38 + 44;
  return {"eyebrow":64, "big":(b.size||92)*1.18, "sub":58, "row":78, "delta":78, "chips":0, "source":0, "gap":24}[b.k]; }
function photoLayer(comp, name, path, cx, cy, h, maxw){ // still image fitted to height h (and maxw), thin border
  var f = app.project.importFile(new ImportOptions(new File(path))); var L = comp.layers.add(f); L.name = name;
  var sc = Math.min(h / f.height, (maxw||9999) / f.width) * 100; L.property("Transform").property("Scale").setValue([sc, sc]);
  L.property("Transform").property("Position").setValue([cx, cy]);
  var bd = rect(comp, name+"_bd", cx, cy, f.width*sc/100 + 4, f.height*sc/100 + 4, null, DEEP, 4, 2); return [L, bd];
}
function chipsLayout(items, x0, w){ var rows=[[]], cx=0; for (var i=0;i<items.length;i++){ var cw=items[i][0].length*18+48; if (cx+cw>w && rows[rows.length-1].length){ rows.push([]); cx=0; } rows[rows.length-1].push([items[i], cx, cw]); cx+=cw+14; } return rows; }
function drawBlocks(comp, g, c, t, tin, x0, cw, centre){
  var B = g.blocks, H = 0, all = [], keep = [];
  for (var i=0;i<B.length;i++){ if (B[i].k=="chips") H += chipsLayout(B[i].items, 0, cw).length*70; else if (B[i].k!="source") H += blockH(B[i], cw); }
  var y = (g.top!==undefined) ? g.top : Math.max(110, 540 - H/2 - 20), rowN = 0;
  for (var i=0;i<B.length;i++){ var b = B[i], tc = Math.max(tin, b.cue!==undefined ? t(c[b.cue]) : tin);
    if (b.k=="eyebrow"){ var ln = line(comp,"eb"+i,x0,y+18,x0+46,y+18,RED,4); draw(ln,tc,0.3);   // tc = tin unless the eyebrow has its own spoken cue
      var et = text(comp,b.text,FM,26,DIM,x0+62,y+27,ParagraphJustification.LEFT_JUSTIFY,150); reveal(et,tc+0.05,10,0.4); keep.push(comp.layer("eb"+i), et); y += 64; }
    else if (b.k=="big"){ var sz = b.size||92, by = y + sz*0.82;
      if (b.from!==undefined){ var A = text(comp,b.from,FB,sz,PAPER,x0,by,ParagraphJustification.LEFT_JUSTIFY,-20); reveal(A,tc,18);
        var aw = textW(A), ax = x0+aw+26, ar = arrowR(comp,"ar"+i,ax,ax+70,by-sz*0.33,RED,7); reveal(ar,tc+0.25,0,0.3);
        var Bt = text(comp,b.to,FB,sz,PAPER,ax+100,by,ParagraphJustification.LEFT_JUSTIFY,-20); reveal(Bt,b.cue2!==undefined?Math.max(tin,t(c[b.cue2])):tc+0.35,18); all.push(A,ar,Bt); }
      else { var L = text(comp,b.text,FB,sz,b.tone=="dim"?DIM:PAPER,centre?960:x0,by,centre?ParagraphJustification.CENTER_JUSTIFY:ParagraphJustification.LEFT_JUSTIFY,-20); reveal(L,tc,18); all.push(L); }
      y += sz*1.18; }
    else if (b.k=="sub"){ var S = text(comp,b.text,FM,34,DIM,centre?960:x0,y+38,centre?ParagraphJustification.CENTER_JUSTIFY:ParagraphJustification.LEFT_JUSTIFY); reveal(S,tc,12,0.4); all.push(S); y += 58; }
    else if (b.k=="row"){ var ry = y+39, dv = line(comp,"dv"+i,x0,y,x0+cw,y,DEEP,2); draw(dv,tc,0.3); all.push(comp.layer("dv"+i));
      var mk = markChip(comp,"mk"+i,b.mark||"plus",x0+22,ry,40); revealAll(mk,tc,12,0.4); all = all.concat(mk);
      var R = text(comp,b.text,FS,(b.text.length>26?34:40),PAPER,x0+66,ry+14,ParagraphJustification.LEFT_JUSTIFY); reveal(R,tc+0.04,12,0.4); all.push(R);
      if (b.mark=="strike"){ } y += 78; rowN++; }
    else if (b.k=="chips"){ var CR = chipsLayout(b.items, 0, cw);
      for (var r=0;r<CR.length;r++){ for (var j=0;j<CR[r].length;j++){ var it = CR[r][j], tcc = Math.max(tin, t(c[it[0][1]])), chx = x0+it[1]+it[2]/2, chy = y+30;
          var ch = rect(comp,"chip"+i+"_"+r+"_"+j,chx,chy,it[2],56,null,DIM,8,2); var ct = text(comp,it[0][0],FS,30,PAPER,chx,chy+10);
          reveal(ch,tcc,12,0.4); reveal(ct,tcc+0.03,12,0.4); all.push(ch,ct); } y += 70; } }
    else if (b.k=="delta"){ var ry = y+39, dv = line(comp,"dv"+i,x0,y,x0+cw,y,DEEP,2); draw(dv,tc,0.3); all.push(comp.layer("dv"+i));
      var mk = markChip(comp,"mk"+i,b.mark||"down",x0+22,ry,40); revealAll(mk,tc,12,0.4); all = all.concat(mk);
      var lb = text(comp,b.label,FS,34,PAPER,x0+66,ry+12,ParagraphJustification.LEFT_JUSTIFY); reveal(lb,tc+0.04,12,0.4); all.push(lb);
      var tx2 = x0+cw-(b.unit?0:0), un = null;
      if (b.unit){ un = text(comp,b.unit,FM,22,DIM,x0+cw,ry+11,ParagraphJustification.RIGHT_JUSTIFY); tx2 = x0+cw-textW(un)-10; }
      var tv = text(comp,b.to,FB,38,PAPER,tx2,ry+13,ParagraphJustification.RIGHT_JUSTIFY), tw = textW(tv);
      var ax1 = tx2-tw-56, ar = arrowR(comp,"dar"+i,ax1,ax1+38,ry,(b.mark=="upgood"||b.mark=="down")?GREEN:DIM,5);
      var fv = text(comp,b.from,FM,32,DIM,ax1-12,ry+11,ParagraphJustification.RIGHT_JUSTIFY);
      var t2 = b.cue2!==undefined ? Math.max(tin, t(c[b.cue2])) : tc+0.3;
      reveal(fv,tc+0.06,12,0.4); reveal(ar,t2-0.1,0,0.3); reveal(tv,t2,12,0.4); all.push(fv,ar,tv); if (un){ reveal(un,t2+0.04,12,0.4); all.push(un); }
      y += 78; }
    else if (b.k=="photos"){ var ph = b.h||340, n = b.items.length, gap = 24, pw = Math.min((cw-(n-1)*gap)/n, ph*0.62), px0 = x0 + (cw - (n*pw+(n-1)*gap))/2;
      for (var j=0;j<n;j++){ var it = b.items[j], pcx = px0 + pw/2 + j*(pw+gap), tp = Math.max(tin, t(c[it.cue]));
        var pl = photoLayer(comp,"ph"+i+"_"+j,it.img,pcx,y+ph/2,ph,pw); revealAll(pl,tp,14,0.45); all = all.concat(pl);
        var lt = text(comp,it.label,FM,22,DIM,pcx,y+ph+32,ParagraphJustification.CENTER_JUSTIFY,60); reveal(lt,tp+0.05,8,0.4); all.push(lt); }
      y += ph + 50; }
    else if (b.k=="quote"){ var nl = quoteLines(b, cw), qh = 52 + nl*38 + 44, qc = rect(comp,"q"+i,x0+cw/2,y+qh/2,cw,qh,PAPER,null,12);
      var qm = text(comp,"\u201C",FB,56,RED,x0+20,y+58,ParagraphJustification.LEFT_JUSTIFY);
      var qt = boxtext(comp,b.text,FS,30,INK,x0+64,y+30+nl*19,cw-96,nl*38+8,ParagraphJustification.LEFT_JUSTIFY,38);
      var qa = text(comp,b.attr,FM,22,DEEP,x0+64,y+qh-22,ParagraphJustification.LEFT_JUSTIFY);
      reveal(qc,tc,14,0.45); reveal(qm,tc+0.05,14,0.45); reveal(qt,tc+0.08,14,0.45); reveal(qa,tc+0.14,14,0.45); all.push(qc,qm,qt,qa); y += qh + 12; }
    else if (b.k=="source"){ var sc = text(comp,b.text,FM,20,DIM,centre?960:x0,(b.text.indexOf("\r")>=0?1012:1040),centre?ParagraphJustification.CENTER_JUSTIFY:ParagraphJustification.LEFT_JUSTIFY,20); reveal(sc,tc+0.2,8,0.4); all.push(sc); }
    else if (b.k=="gap"){ y += 24; }
  }
  return {all:all, keep:keep};
}
T.rsplit = function(comp, g, c, t){
  var T0 = t(g.start), T1 = t(g.end), tin = plate(comp, g, T0, T1), out = t(c.out);
  var r = drawBlocks(comp, g, c, t, tin, CX0, CXW, false);
  if (g.final && g.final.photo){ var tf = t(c.final); hideAll(r.all.concat(r.keep), tf-0.12); r.keep = []; var F = g.final, ph = F.photo_h||480, nq = F.quote ? quoteLines({text:F.quote}, CXW) : 0;
    var qh = F.quote ? 52 + nq*38 + 44 : 0, tot = ph + 44 + (qh ? qh + 18 : 0), y0 = 540 - tot/2;
    var pl = photoLayer(comp,"fph",F.photo,CX0+CXW/2,y0+ph/2,ph,CXW); revealAll(pl,tf,16,0.5); r.all = pl;
    var lt = text(comp,F.label,FM,24,DIM,CX0+CXW/2,y0+ph+34,ParagraphJustification.CENTER_JUSTIFY,60); reveal(lt,tf+0.06,10,0.4); r.all.push(lt);
    if (F.quote){ var qy = y0+ph+44+18, qc = rect(comp,"fq",CX0+CXW/2,qy+qh/2,CXW,qh,PAPER,null,12), qm = text(comp,"\u201C",FB,56,RED,CX0+20,qy+58,ParagraphJustification.LEFT_JUSTIFY);
      var qt = boxtext(comp,F.quote,FS,30,INK,CX0+64,qy+30+nq*19,CXW-96,nq*38+8,ParagraphJustification.LEFT_JUSTIFY,38), qa = text(comp,F.attr,FM,22,DEEP,CX0+64,qy+qh-22,ParagraphJustification.LEFT_JUSTIFY);
      var tq = c.quote!==undefined ? t(c.quote) : tf+0.3; reveal(qc,tq,14,0.45); reveal(qm,tq+0.05,14,0.45); reveal(qt,tq+0.08,14,0.45); reveal(qa,tq+0.14,14,0.45); r.all = r.all.concat([qc,qm,qt,qa]); }
  } else if (g.final){ var tf = t(c.final); hideAll(r.all, tf-0.12);
    var two = g.final.title.indexOf("\r")>=0, fy = (g.final.y||565), fc = rect(comp,"final",CX0+CXW/2,fy,CXW,(two?200:130)+(g.final.sub?70:0),PAPER,null,14);
    var ft = boxtext(comp,g.final.title,FB,62,INK,CX0+CXW/2,fy-(g.final.sub?32:0),CXW-60,two?160:90,ParagraphJustification.CENTER_JUSTIFY,68);
    reveal(fc,tf,20); reveal(ft,tf+0.05,20); r.all = [fc,ft];
    if (g.final.sub){ var fs = text(comp,g.final.sub,FM,30,DEEP,CX0+CXW/2,fy+(two?100:56)); reveal(fs,tf+0.1,16); r.all.push(fs); } }
  hideAll(r.all.concat(r.keep), out);
};
T.fblocks = function(comp, g, c, t){ // full-frame scene: centred column of blocks (use with g.full)
  var tin = t(c.card)+0.15, w = g.cw||1000, x0 = 960 - w/2; var r = drawBlocks(comp, g, c, t, tin, x0, w, !!g.centre);
  if (g.final){ var tf = t(c.final); hideAll(r.all, tf-0.12); var ft = boxtext(comp,g.final.title,FB,84,PAPER,960,500,1500,220,ParagraphJustification.CENTER_JUSTIFY,92); reveal(ft,tf,22,0.5);
    var fs = g.final.sub ? text(comp,g.final.sub,FM,36,DIM,960,640) : null; if (fs) reveal(fs,tf+0.12,14,0.45); r.all = [ft]; if (fs) r.all.push(fs); }
  hideAll(r.all.concat(r.keep), t(c.out));
};
T.chain = function(comp, g, c, t){ // full-frame mechanism chain: nodes [[text, cue]] left to right, then fan chips [[text, cue]] under it, then a closing line
  var N = g.nodes, n = N.length, w = g.nw||330, gap = 90, x0 = 960 - (n*w+(n-1)*gap)/2, y = g.ny||(g.fan?420:470), all = [];
  if (g.head){ var ln = line(comp,"ebl",960-200,y-150,960-154,y-150,RED,4); draw(ln,t(c.card)+0.1,0.3);
    var et = text(comp,g.head,FM,28,DIM,960-138,y-141,ParagraphJustification.LEFT_JUSTIFY,150); reveal(et,t(c.card)+0.15,10,0.4); all.push(comp.layer("ebl"),et); }
  for (var k=0;k<n;k++){ var cx = x0+w/2+k*(w+gap), tc = Math.max(t(c.card)+0.2, t(c[N[k][1]]));
    var R = rect(comp,"node"+k,cx,y,w,150,k==n-1&&g.lastRed?RED:DEEP,null,14); var L = boxtext(comp,N[k][0],FS,38,PAPER,cx,y,w-36,120,ParagraphJustification.CENTER_JUSTIFY,44);
    reveal(R,tc,16); reveal(L,tc+0.04,16); all.push(R,L);
    if (k>0){ var a = arrowR(comp,"arw"+k,cx-w/2-gap+14,cx-w/2-14,y,DIM,6); reveal(a,tc-0.1,0,0.25); all.push(a); } }
  if (g.fan){ var F = g.fan, fg = 22, fy = y+230, fts = [], fws = [], tot = 0;
    for (var k=0;k<F.length;k++){ var ft = text(comp,F[k][0],FS,32,INK,0,fy+11); fts.push(ft); fws.push(textW(ft)+78); tot += fws[k]; }
    tot += fg*(F.length-1); var fx = 960 - tot/2;
    for (var k=0;k<F.length;k++){ var cxk = fx + fws[k]/2, tf = Math.max(t(c.card)+0.2, t(c[F[k][1]])), tw = textW(fts[k]);
      fts[k].property("Transform").property("Position").setValue([cxk-14, fy+11]);
      var ch = rect(comp,"fan"+k,cxk,fy,fws[k],74,PAPER,null,10); ch.moveAfter(fts[k]);
      var ax = cxk-14+tw/2+25, up = pathL(comp,"fanup"+k,[[ax-12,fy+2],[ax,fy-12],[ax+12,fy+2],[ax,fy-12],[ax,fy+14]],RED,4);
      reveal(ch,tf,12,0.4); reveal(fts[k],tf+0.03,12,0.4); reveal(up,tf+0.06,12,0.4); all.push(ch,fts[k],up); fx += fws[k] + fg; } }
  if (g.close){ var cl = text(comp,g.close[0],FB,64,PAPER,960,(g.fan?y+400:y+260)); reveal(cl,Math.max(t(c.card)+0.2,t(c[g.close[1]])),18); all.push(cl); }
  hideAll(all, t(c.out));
};
T.compare2 = function(comp, g, c, t){ // full-frame: two columns (e.g. MONTH 0 | MONTH 6), rows land on cues, centre tag on c.mid
  var all = [], cols = g.cols, cw = 560, xs = [960-cw/2-60, 960+cw/2+60], top = 330;
  for (var k=0;k<2;k++){ var col = cols[k], tc = Math.max(t(c.card)+0.15, t(c[col.cue]));
    var hd = rect(comp,"hd"+k,xs[k],top,cw,110,k?PAPER:DEEP,null,12); var ht = text(comp,col.head,FB,52,k?INK:PAPER,xs[k],top+18);
    reveal(hd,tc,16); reveal(ht,tc+0.04,16); all.push(hd,ht);
    for (var j=0;j<col.rows.length;j++){ var ry = top+130+j*96+48, tr = Math.max(tc+0.1, t(c[col.rows[j][1]]));
      var rr = rect(comp,"r"+k+"_"+j,xs[k],ry,cw,84,null,DEEP,10,2); var rt = text(comp,col.rows[j][0],FS,38,k?PAPER:DIM,xs[k],ry+13);
      reveal(rr,tr,12,0.4); reveal(rt,tr+0.03,12,0.4); all.push(rr,rt); } }
  if (g.mid){ var tm = t(c[g.mid[1]]); var mt = text(comp,g.mid[0],FB,58,PAPER,960,760); reveal(mt,tm,18); all.push(mt); }
  var ar = arrowR(comp,"mid_ar",960-40,960+40,top,DIM,6); reveal(ar,Math.max(t(c.card)+0.15,t(c[cols[1].cue]))-0.1,0,0.3); all.push(ar);
  hideAll(all, t(c.out));
};
T.cta169 = function(comp, g, c, t){ // button on the lower third, arrow nudges down twice; optional steps line under it
  var Y = g.y||820, BW = g.w||620, X = g.x||960;
  var btn = rect(comp,"btn",X,Y,BW,104,PAPER,null,52); var bt = text(comp,g.text,FB,46,INK,X-30,Y+16);
  var ax = X+textW(bt)/2+4, ar = pathL(comp,"btn_ar",[[ax-14,Y-6],[ax,Y+8],[ax+14,Y-6],[ax,Y+8],[ax,Y-16]],INK,5);
  var tb = t(c.btn); reveal(btn,tb,22,0.45); reveal(bt,tb+0.04,22,0.45); reveal(ar,tb+0.08,22,0.45);
  var ap = ar.property("Transform").property("Position"), v = ap.valueAtTime(tb+0.6,false);
  for (var k=0;k<2;k++){ var s0 = tb+0.9+k*0.7; ap.setValueAtTime(s0,v); ap.setValueAtTime(s0+0.18,[v[0],v[1]+9]); ap.setValueAtTime(s0+0.36,v); }
  var all = [btn,bt,ar];
  if (g.steps){ var S = g.steps, sx = X - (S.length-1)*180, pill = rect(comp,"steps_bg",X,Y+104,S.length*360+40,62,INK,null,31); reveal(pill,tb+0.15,10,0.4); all.push(pill);
    for (var k=0;k<S.length;k++){ var st = text(comp,(k+1)+"  "+S[k][0],FS,30,PAPER,sx+k*360,Y+114);
      reveal(st,Math.max(tb+0.2,t(c[S[k][1]])),10,0.4); all.push(st); } }
  hideAll(all, t(c.out));
};
T.name169 = function(comp, g, c, t){ // name tag bottom-left for client clips
  var X = g.x||70, Y = g.y||940, w = Math.max(g.name.length*27, (g.role||"").length*16)+70;
  var R = rect(comp,"tag",X+w/2,Y,w,(g.role?108:76),PAPER,null,10), bar = rect(comp,"bar",X+6,Y,12,(g.role?108:76),INK,null,0);
  var nm = text(comp,g.name,FB,44,INK,X+34,Y+(g.role?-4:15),ParagraphJustification.LEFT_JUSTIFY), all = [R,bar,nm];
  reveal(R,t(c.card),16); reveal(bar,t(c.card),16); reveal(nm,t(c.card)+0.06,16);
  if (g.role){ var rl = text(comp,g.role,FM,26,DEEP,X+34,Y+36,ParagraphJustification.LEFT_JUSTIFY); reveal(rl,t(c.card)+0.1,16); all.push(rl); }
  hideAll(all, t(c.out));
};
T.still = function(comp, g, c, t){ // Higgsfield still: covers the frame, slow push (100 -> g.zoom) with a little drift; opaque
  var f = app.project.importFile(new ImportOptions(new File(g.image))); var L = comp.layers.add(f);
  var sc = Math.max(1920/f.width, 1080/f.height)*100, z = g.zoom||1.08, s = L.property("Transform").property("Scale"), p = L.property("Transform").property("Position");
  var D = comp.duration; s.setValueAtTime(0,[sc,sc]); s.setValueAtTime(D,[sc*z,sc*z]);
  p.setValueAtTime(0,[960,540]); p.setValueAtTime(D,[960+(g.dx||0),540+(g.dy||0)]);
};

// ---------------------------------------------------------------- render
app.beginSuppressDialogs();
try { if (app.project) app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch(e){}
app.newProject();
var rq = app.project.renderQueue;
for (var gi=0; gi<G.length; gi++){
  var g = G[gi], c = g.cues, T0 = g.start, dur = g.end - g.start;
  if (typeof ONLY != 'undefined' && ONLY.length) { var hit=false; for (var oi=0; oi<ONLY.length; oi++) if (ONLY[oi]==g.id) hit=true; if (!hit) continue; }
  if (c.out===undefined && g.type!="cta") c.out = g.end - 0.25;
  var comp = app.project.items.addComp(g.id, CW, CH, 1, dur, FPS);
  var t = (function(T0){ return function(x){ return x - T0; }; })(T0);
  if (!T[g.type]) { app.project.save(new File(OUT + "ERR_unknown_type_" + g.id + ".aep")); continue; }
  // g.full: opaque full-frame scene. Background + content slide in from the right on c.card (0.22 s) and out to the
  // left on c.out (0.20 s), so it reads like a cut, not an overlay. Keep content between y 250 and 1150 (captions at 1280).
  if (g.full) rect(comp,"bg",CW/2,CH/2,CW,CH,(g.bg=="paper"?PAPER:INK),null,0);
  try { T[g.type](comp, g, c, t); }
  catch(err){ app.project.save(new File(OUT + "ERR_" + g.id + "_line" + err.line + "_" + String(err.message).replace(/[^A-Za-z0-9]+/g, "-").substr(0, 60) + ".aep")); continue; }
  if (g.full){
    // null pinned at frame centre so g.scale (e.g. 1.25) grows the scene about the middle; the background is not scaled
    var nl=comp.layers.addNull(); nl.property("Transform").property("Anchor Point").setValue([CW/2,CH/2]); nl.property("Transform").property("Position").setValue([CW/2,CH/2]);
    for (var li=2; li<=comp.numLayers; li++){ var LL=comp.layer(li); if (!LL.parent) LL.setParentWithJump(nl); }
    var sc=(g.scale||1)*100, bgl=comp.layer("bg"); if (sc!=100){ nl.property("Transform").property("Scale").setValue([sc,sc]); bgl.property("Transform").property("Scale").setValue([10000/sc,10000/sc]); }
    var np=nl.property("Transform").property("Position"), tin=t(c.card!==undefined?c.card:g.start+0.05), tout=t(c.out);
    np.setValueAtTime(Math.max(0,tin-0.02),[CW*1.5,CH/2]); np.setValueAtTime(tin+0.2,[CW/2,CH/2]); np.setValueAtTime(tout,[CW/2,CH/2]); np.setValueAtTime(tout+0.2,[-CW/2,CH/2]); ease(np);
  }
  var item = rq.items.add(comp); var om = item.outputModule(1);
  om.applyTemplate("High Quality with Alpha"); om.file = new File(OUT + g.id + ".mov");
}
app.project.save(new File(AEP));
rq.render();
app.project.save();
app.endSuppressDialogs(false);
})();
