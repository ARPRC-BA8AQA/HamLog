(function () {
  const canvas = document.querySelector('#canvas');
  const ctx = canvas.getContext('2d');
  const projectName = document.querySelector('#project-name');
  const statusLabel = document.querySelector('#save-status');
  const layersTarget = document.querySelector('#layers');
  const inspector = document.querySelector('#inspector');
  const bindingSelect = document.querySelector('#binding-field');
  const exportPopover = document.querySelector('#export-popover');
  const projectsDialog = document.querySelector('#projects-dialog');
  const {escapeHtml, uid, downloadText, dateTime} = HamLogUtils;
  const PX_PER_MM = 10;
  const HANDLE_SIZE = 13;
  const imageCache = new Map();
  const fallbackFields = [
    {key:'log.callsign',label:'对方呼号',group:'通联'}, {key:'log.date',label:'通联日期',group:'通联'},
    {key:'log.freq',label:'频率',group:'通联'}, {key:'log.mode',label:'模式',group:'通联'},
    {key:'log.rst',label:'信号报告',group:'通联'}, {key:'log.qth',label:'对方 QTH',group:'通联'},
    {key:'station.my_callsign',label:'我的呼号',group:'本台'}, {key:'station.my_name',label:'我的姓名',group:'本台'},
    {key:'station.my_qth',label:'我的 QTH',group:'本台'}, {key:'station.my_grid',label:'我的网格',group:'本台'},
    {key:'meta.export_date',label:'导出日期',group:'元数据'}, {key:'meta.export_time',label:'导出时间',group:'元数据'}
  ];
  const typeNames = {text:'文字',rect:'矩形',circle:'圆形',ellipse:'椭圆',line:'线条',image:'图片',qrcode:'二维码',unknown:'未知元素'};
  const typeIcons = {text:'T',rect:'□',circle:'○',ellipse:'○',line:'╱',image:'▧',qrcode:'▦',unknown:'?'};
  let projectId = null;
  let selectedId = null;
  let dirty = false;
  let dragging = null;
  let previewData = null;
  let fields = fallbackFields;
  let history = [];
  let historyIndex = -1;
  let historyTimer = null;

  function initialDocument() {
    const created = new Date().toISOString();
    return {
      schema_version:'1.0', format:'hamlog-qsl',
      meta:{name:'标准 QSL 卡片',author:'',description:'',created_at:created,updated_at:created,app_version:'Release 2.0.0'},
      canvas:{width:148,height:105,unit:'mm',dpi:300,bleed:3,orientation:'landscape'},
      background:{type:'color',color:'#f7faf9'}, assets:{}, guides:[],
      elements:[
        {id:uid('el'),type:'rect',name:'卡片边框',x:4,y:4,w:140,h:97,rotation:0,opacity:1,visible:true,locked:false,style:{fill:'transparent',fill_opacity:1,border_color:'#2d5158',border_width:0.8,border_style:'solid',radius:2}},
        {id:uid('el'),type:'text',name:'QSL 标题',x:10,y:8,w:93,h:11,rotation:0,opacity:1,visible:true,locked:false,content:'QSL CARD',style:{font_family:'Arial',font_size:21,font_weight:'bold',color:'#16343b',align:'left',valign:'middle',line_height:1.2,letter_spacing:0}},
        {id:uid('el'),type:'text',name:'对方呼号',x:10,y:27,w:96,h:17,rotation:0,opacity:1,visible:true,locked:false,binding:'log.callsign',content:'{log.callsign}',style:{font_family:'Arial',font_size:34,font_weight:'bold',color:'#147d80',align:'left',valign:'middle',line_height:1.1,letter_spacing:0}},
        {id:uid('el'),type:'text',name:'通联详情',x:10,y:49,w:98,h:25,rotation:0,opacity:1,visible:true,locked:false,content:'DATE  {log.date}\nFREQ  {log.freq}   MODE  {log.mode}\nRST   {log.rst}',style:{font_family:'Arial',font_size:10,font_weight:'normal',color:'#344b54',align:'left',valign:'top',line_height:1.45,letter_spacing:0}},
        {id:uid('el'),type:'text',name:'本台呼号',x:10,y:84,w:93,h:9,rotation:0,opacity:1,visible:true,locked:false,binding:'station.my_callsign',content:'73 DE {station.my_callsign}',style:{font_family:'Arial',font_size:13,font_weight:'bold',color:'#16343b',align:'left',valign:'middle',line_height:1.2,letter_spacing:0}},
        {id:uid('el'),type:'qrcode',name:'呼号二维码',x:118,y:72,w:20,h:20,rotation:0,opacity:1,visible:true,locked:false,binding:'log.callsign',content:'{log.callsign}',style:{fg_color:'#17373d',bg_color:'#ffffff',ecc_level:'M'}}
      ]
    };
  }
  let doc = initialDocument();

  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function clamp(value, min, max) { return Math.min(max, Math.max(min, Number(value) || 0)); }
  function unitToMm(value,unit,dpi){if(unit==='cm')return value*10;if(unit==='in')return value*25.4;if(unit==='px')return value/Math.max(72,dpi||300)*25.4;return value;}
  function mmToUnit(value,unit,dpi){if(unit==='cm')return value/10;if(unit==='in')return value/25.4;if(unit==='px')return value/25.4*Math.max(72,dpi||300);return value;}
  function inCurrentUnit(mm){return mmToUnit(mm,doc.canvas.unit,doc.canvas.dpi||300);}
  function displayScale() { const unit=doc.canvas.unit;const base=unit==='cm'?PX_PER_MM*10:unit==='in'?PX_PER_MM*25.4:unit==='px'?1:PX_PER_MM;return Math.min(base,1800/Math.max(1,doc.canvas.width),1300/Math.max(1,doc.canvas.height)); }
  function exportScale(dpi) { const unit=doc.canvas.unit;if(unit==='cm')return dpi/2.54;if(unit==='in')return dpi;if(unit==='px')return 1;return dpi/25.4; }
  function unitBounds(){return{min:mmToUnit(20,doc.canvas.unit,doc.canvas.dpi),max:mmToUnit(1000,doc.canvas.unit,doc.canvas.dpi)};}
  function selected() { return doc.elements.find(element => element.id === selectedId) || null; }
  function markDirty(options) {
    dirty = true; statusLabel.textContent = '有未保存更改';
    clearTimeout(historyTimer);
    if (!(options && options.noHistory)) historyTimer = setTimeout(pushHistory, 180);
  }
  function pushHistory() {
    const snapshot = JSON.stringify(doc);
    if (history[historyIndex] === snapshot) return;
    history = history.slice(0, historyIndex + 1); history.push(snapshot);
    if (history.length > 50) history.shift(); else historyIndex++;
    updateHistoryButtons();
  }
  function resetHistory() { history = [JSON.stringify(doc)]; historyIndex = 0; updateHistoryButtons(); }
  function updateHistoryButtons() { document.querySelector('#undo').disabled = historyIndex <= 0; document.querySelector('#redo').disabled = historyIndex >= history.length - 1; }
  function restoreHistory(index) { if (index < 0 || index >= history.length) return; historyIndex = index; doc = normalizeDocument(JSON.parse(history[index])); selectedId = null; syncDocumentControls(); renderAll(); markDirty({noHistory:true}); updateHistoryButtons(); }

  function normalizeElement(raw, index) {
    const type = ['text','rect','circle','ellipse','line','image','qrcode'].includes(raw && raw.type) ? raw.type : 'unknown';
    const element = Object.assign({id:uid('el'),type,name:typeNames[type] || '未知元素',x:10+index*2,y:10+index*2,w:type === 'line' ? 35 : 30,h:type === 'line' ? 0 : 12,rotation:0,opacity:1,visible:true,locked:false,style:{}}, raw || {});
    element.id = String(element.id || uid('el')); element.type = type;
    if (type === 'unknown' && raw) element.unknown_type = raw.unknown_type || raw.type || 'unknown';
    ['x','y','w','h','rotation','opacity'].forEach(key => { element[key] = Number(element[key]) || 0; });
    element.visible = element.visible !== false; element.locked = element.locked === true; element.style = element.style && typeof element.style === 'object' ? element.style : {};
    return element;
  }
  function normalizeDocument(raw) {
    const value = raw && typeof raw === 'object' ? raw : {};
    const canvasValue = value.canvas && typeof value.canvas === 'object' ? value.canvas : {};
    return {
      schema_version:'1.0', format:'hamlog-qsl',
      meta:Object.assign({name:'未命名卡片',created_at:new Date().toISOString(),app_version:'Release 2.0.0'}, value.meta || {}),
      canvas:Object.assign({width:148,height:105,unit:'mm',dpi:300,bleed:0,orientation:'landscape'}, canvasValue, {width:clamp(canvasValue.width || 148,0.1,10000),height:clamp(canvasValue.height || 105,0.1,10000),unit:['mm','px','in','cm'].includes(canvasValue.unit) ? canvasValue.unit : 'mm'}),
      background:value.background && typeof value.background === 'object' ? value.background : {type:'color',color:'#ffffff'},
      elements:Array.isArray(value.elements) ? value.elements.map(normalizeElement) : [],
      assets:value.assets && typeof value.assets === 'object' ? value.assets : {}, guides:Array.isArray(value.guides) ? value.guides : []
    };
  }

  function resizeCanvas() {
    const scale=displayScale();canvas.width = Math.max(1, Math.round(doc.canvas.width * scale));
    canvas.height = Math.max(1, Math.round(doc.canvas.height * scale));
    document.querySelector('.canvas-stage').style.aspectRatio = `${doc.canvas.width} / ${doc.canvas.height}`;
    document.querySelector('#canvas-size-label').textContent = `${doc.canvas.width} × ${doc.canvas.height} ${doc.canvas.unit}`;
  }
  function getImage(source) {
    if (!source) return null; if (imageCache.has(source)) return imageCache.get(source);
    const image = new Image(); image.onload = draw; image.src = source; imageCache.set(source, image); return image;
  }
  function assetSource(element) { return element.dataurl || doc.assets[element.ref] && doc.assets[element.ref].dataurl || ''; }
  function replaceBindings(text, data, keepPlaceholder) {
    return String(text == null ? '' : text).replace(/\{([^}|]+)(?:\|[^}]+)?\}/g, (match, key) => Object.prototype.hasOwnProperty.call(data || {}, key.trim()) ? String(data[key.trim()] == null ? '' : data[key.trim()]) : keepPlaceholder ? match : '');
  }
  function roundedRect(context,x,y,w,h,r) { const radius=Math.min(Math.abs(w)/2,Math.abs(h)/2,Math.max(0,r||0)); context.beginPath(); context.roundRect(x,y,w,h,radius); }
  function fontPixels(element,scale){return Math.max(1,Number((element.style||{}).font_size||14)*scale*inCurrentUnit(1)*25.4/72);}
  function fontString(element, scale) { const style=element.style||{}; return `${style.font_style||'normal'} ${style.font_weight||'normal'} ${fontPixels(element,scale)}px ${style.font_family||'Arial, sans-serif'}`; }
  function textLines(context, text, maxWidth) {
    const output=[]; String(text).split('\n').forEach(paragraph => { const words=paragraph.split(/(\s+)/); let line=''; words.forEach(word => { const test=line+word; if (line && context.measureText(test).width>maxWidth) { output.push(line.trimEnd()); line=word.trimStart(); } else line=test; }); output.push(line); }); return output.length ? output : [''];
  }
  function drawQrPlaceholder(context, element, x, y, w, h, data) {
    const style=element.style||{}; context.fillStyle=style.bg_color||'#fff'; context.fillRect(x,y,w,h); context.fillStyle=style.fg_color||'#000';
    const content=replaceBindings(element.content||element.binding||'QR',data,true); const cells=21; const cell=Math.min(w,h)/cells; const offsetX=x+(w-cell*cells)/2, offsetY=y+(h-cell*cells)/2;
    function finder(cx,cy) { context.fillRect(offsetX+cx*cell,offsetY+cy*cell,7*cell,7*cell); context.fillStyle=style.bg_color||'#fff'; context.fillRect(offsetX+(cx+1)*cell,offsetY+(cy+1)*cell,5*cell,5*cell); context.fillStyle=style.fg_color||'#000'; context.fillRect(offsetX+(cx+2)*cell,offsetY+(cy+2)*cell,3*cell,3*cell); }
    finder(0,0); finder(14,0); finder(0,14); let hash=0; for(let i=0;i<content.length;i++) hash=((hash<<5)-hash+content.charCodeAt(i))|0;
    for(let row=0;row<cells;row++) for(let col=0;col<cells;col++) { if ((row<8&&col<8)||(row<8&&col>12)||(row>12&&col<8)) continue; hash=(hash*1664525+1013904223)|0; if ((hash>>>28)&1) context.fillRect(offsetX+col*cell,offsetY+row*cell,Math.ceil(cell),Math.ceil(cell)); }
  }
  function renderElement(context, element, scale, data) {
    if (element.visible === false) return; const x=element.x*scale,y=element.y*scale,w=element.w*scale,h=element.h*scale,style=element.style||{};
    context.save(); context.globalAlpha=clamp(element.opacity == null ? 1 : element.opacity,0,1); const cx=x+w/2,cy=y+h/2; context.translate(cx,cy); context.rotate((Number(element.rotation)||0)*Math.PI/180); context.translate(-cx,-cy);
    context.lineWidth=Math.max(.5,Number(style.border_width==null?0.5:style.border_width)*scale); context.strokeStyle=style.border_color||'#263746'; context.setLineDash(style.border_style==='dashed'?[4*scale,3*scale]:style.border_style==='dotted'?[1*scale,2*scale]:[]);
    if (element.type==='rect'||element.type==='circle'||element.type==='ellipse') {
      context.fillStyle=style.fill||'transparent'; context.globalAlpha*=clamp(style.fill_opacity==null?1:style.fill_opacity,0,1);
      if (element.type==='rect') { roundedRect(context,x,y,w,h,Number(style.radius||0)*scale); } else { context.beginPath(); context.ellipse(cx,cy,Math.abs(w/2),Math.abs(h/2),0,0,Math.PI*2); }
      if (style.fill&&style.fill!=='transparent') context.fill(); if (Number(style.border_width||0)>0) context.stroke();
    } else if (element.type==='line') { context.beginPath(); context.moveTo(x,y); context.lineTo(x+w,y+h); context.stroke(); }
    else if (element.type==='text') {
      context.globalAlpha=clamp(element.opacity==null?1:element.opacity,0,1); context.fillStyle=style.color||'#17232b'; context.font=fontString(element,scale); context.textBaseline='top';
      const text=replaceBindings(element.content||'',data,true); const lines=textLines(context,text,Math.max(1,w)); const fontSize=fontPixels(element,scale); const lineHeight=fontSize*Number(style.line_height||1.2); const total=lines.length*lineHeight; let ty=y;
      if(style.valign==='middle') ty=y+(h-total)/2; else if(style.valign==='bottom') ty=y+h-total;
      lines.forEach(line=>{ let tx=x; if(style.align==='center') tx=x+w/2; else if(style.align==='right') tx=x+w; context.textAlign=style.align||'left'; context.fillText(line,tx,ty,Math.max(1,w)); ty+=lineHeight; });
    } else if (element.type==='image') {
      const image=getImage(assetSource(element)); if(image&&image.complete&&image.naturalWidth){ const fit=element.fit||'contain'; let dw=w,dh=h,dx=x,dy=y; if(fit!=='stretch'){ const ratio=fit==='cover'?Math.max(w/image.naturalWidth,h/image.naturalHeight):Math.min(w/image.naturalWidth,h/image.naturalHeight); dw=image.naturalWidth*ratio;dh=image.naturalHeight*ratio;dx=x+(w-dw)/2;dy=y+(h-dh)/2; context.beginPath();context.rect(x,y,w,h);context.clip(); } context.drawImage(image,dx,dy,dw,dh); } else { context.fillStyle='#edf1f2';context.fillRect(x,y,w,h);context.strokeRect(x,y,w,h);context.fillStyle='#78878f';context.font=`${4*scale}px sans-serif`;context.textAlign='center';context.fillText('IMAGE',cx,cy-2*scale); }
    } else if (element.type==='qrcode') drawQrPlaceholder(context,element,x,y,w,h,data);
    else { context.fillStyle='#f3eeee'; context.fillRect(x,y,w,h); context.strokeStyle='#a74442'; context.strokeRect(x,y,w,h); context.fillStyle='#a74442'; context.font=`${3*scale}px sans-serif`; context.textAlign='center'; context.fillText(`UNKNOWN: ${element.unknown_type||''}`,cx,cy); }
    context.restore();
  }
  function drawBackground(context, width, height, scale) {
    const bg=doc.background||{}; context.save(); context.fillStyle=bg.color||'#fff'; context.fillRect(0,0,width,height);
    if(bg.type==='gradient'&&bg.gradient){ const gradient=bg.gradient.direction==='horizontal'?context.createLinearGradient(0,0,width,0):bg.gradient.direction==='diagonal'?context.createLinearGradient(0,0,width,height):context.createLinearGradient(0,0,0,height); (bg.gradient.stops||[]).forEach(stop=>gradient.addColorStop(clamp(stop.offset,0,1),stop.color)); context.fillStyle=gradient;context.fillRect(0,0,width,height); }
    if(bg.type==='image'){ const source=bg.dataurl||doc.assets[bg.ref]&&doc.assets[bg.ref].dataurl;const image=getImage(source);if(image&&image.complete&&image.naturalWidth){context.globalAlpha=clamp(bg.opacity==null?1:bg.opacity,0,1);const ratio=bg.fit==='contain'?Math.min(width/image.naturalWidth,height/image.naturalHeight):Math.max(width/image.naturalWidth,height/image.naturalHeight);const w=bg.fit==='stretch'?width:image.naturalWidth*ratio,h=bg.fit==='stretch'?height:image.naturalHeight*ratio;context.drawImage(image,(width-w)/2,(height-h)/2,w,h);}}
    context.restore();
  }
  function draw() {
    const scale=displayScale();ctx.clearRect(0,0,canvas.width,canvas.height); drawBackground(ctx,canvas.width,canvas.height,scale); doc.elements.forEach(element=>renderElement(ctx,element,scale,previewData||{}));
    const element=selected(); if(element&&element.visible!==false){ const x=element.x*scale,y=element.y*scale,w=element.w*scale,h=element.h*scale;ctx.save();ctx.strokeStyle='#0a8e93';ctx.lineWidth=2;ctx.setLineDash([6,4]);ctx.strokeRect(Math.min(x,x+w)-2,Math.min(y,y+h)-2,Math.abs(w)+4,Math.max(Math.abs(h),4)+4);ctx.setLineDash([]);ctx.fillStyle=element.locked?'#78878f':'#fff';ctx.strokeStyle='#0a8e93';ctx.lineWidth=2;ctx.fillRect(x+w-HANDLE_SIZE/2,y+h-HANDLE_SIZE/2,HANDLE_SIZE,HANDLE_SIZE);ctx.strokeRect(x+w-HANDLE_SIZE/2,y+h-HANDLE_SIZE/2,HANDLE_SIZE,HANDLE_SIZE);ctx.restore();}
  }
  function renderLayers() {
    document.querySelector('#layer-count').textContent=`${doc.elements.length} 个元素`;
    layersTarget.innerHTML=doc.elements.length?doc.elements.slice().reverse().map(element=>`<div class="layer${element.id===selectedId?' selected':''}" data-layer="${escapeHtml(element.id)}"><span class="layer-icon">${typeIcons[element.type]||'?'}</span><span class="layer-name">${escapeHtml(element.name||typeNames[element.type]||element.type)}</span><button class="layer-lock" data-visible="${escapeHtml(element.id)}" title="${element.visible===false?'显示':'隐藏'}">${element.visible===false?'○':'●'}</button><button class="layer-lock" data-lock="${escapeHtml(element.id)}" title="${element.locked?'解锁':'锁定'}">${element.locked?'◆':'◇'}</button></div>`).join(''):'<div class="empty-inspector">画布中还没有元素。</div>';
    layersTarget.querySelectorAll('[data-layer]').forEach(row=>row.onclick=event=>{ if(event.target.closest('button'))return;selectedId=row.dataset.layer;renderAll(); });
    layersTarget.querySelectorAll('[data-visible]').forEach(button=>button.onclick=()=>{const element=doc.elements.find(item=>item.id===button.dataset.visible);element.visible=element.visible===false;markDirty();renderAll();});
    layersTarget.querySelectorAll('[data-lock]').forEach(button=>button.onclick=()=>{const element=doc.elements.find(item=>item.id===button.dataset.lock);element.locked=!element.locked;markDirty();renderAll();});
  }
  function inputRow(label,name,value,type,options) { if(type==='select') return `<label>${label}<select name="${name}">${options.map(option=>`<option value="${escapeHtml(option)}"${String(value)===String(option)?' selected':''}>${escapeHtml(option)}</option>`).join('')}</select></label>`; return `<label>${label}<input name="${name}" type="${type||'text'}" value="${escapeHtml(value==null?'':value)}"${type==='number'?' step="0.1"':''}></label>`; }
  function renderInspector() {
    const element=selected(); if(!element){inspector.innerHTML='<div class="section-heading"><h2>属性</h2><span class="muted">选择元素后编辑</span></div><div class="empty-inspector">从画布或图层列表选择元素。</div>';return;}
    const style=element.style||{}; let specific='';
    if(element.type==='text') specific=`<div class="inspector-divider"></div><label>内容<textarea name="content">${escapeHtml(element.content||'')}</textarea></label><div class="inspector-grid">${inputRow('字号','style.font_size',style.font_size||14,'number')}${inputRow('文字色','style.color',style.color||'#17232b','color')}${inputRow('字重','style.font_weight',style.font_weight||'normal','select',['normal','bold','600','800'])}${inputRow('对齐','style.align',style.align||'left','select',['left','center','right'])}</div>`;
    else if(['rect','circle','ellipse'].includes(element.type)) specific=`<div class="inspector-divider"></div><div class="inspector-grid">${inputRow('填充','style.fill',style.fill==='transparent'?'#ffffff':style.fill||'#ffffff','color')}${inputRow('边框','style.border_color',style.border_color||'#263746','color')}${inputRow('边框宽','style.border_width',style.border_width||0,'number')}${element.type==='rect'?inputRow('圆角','style.radius',style.radius||0,'number'):''}</div>`;
    else if(element.type==='line') specific=`<div class="inspector-divider"></div><div class="inspector-grid">${inputRow('线条色','style.border_color',style.border_color||'#263746','color')}${inputRow('线宽','style.border_width',style.border_width||1,'number')}${inputRow('线型','style.border_style',style.border_style||'solid','select',['solid','dashed','dotted'])}</div>`;
    else if(element.type==='image') specific=`<div class="inspector-divider"></div>${inputRow('适应方式','fit',element.fit||'contain','select',['contain','cover','stretch'])}`;
    else if(element.type==='qrcode') specific=`<div class="inspector-divider"></div><label>二维码内容<textarea name="content">${escapeHtml(element.content||'')}</textarea></label><div class="inspector-grid">${inputRow('前景','style.fg_color',style.fg_color||'#000000','color')}${inputRow('背景','style.bg_color',style.bg_color||'#ffffff','color')}${inputRow('纠错','style.ecc_level',style.ecc_level||'M','select',['L','M','Q','H'])}</div>`;
    inspector.innerHTML=`<div class="section-heading"><h2>属性</h2><span class="muted">${escapeHtml(typeNames[element.type]||element.type)}</span></div><form class="inspector-form" id="inspector-form">${inputRow('图层名称','name',element.name||'')}<div class="inspector-grid">${inputRow('X','x',element.x,'number')}${inputRow('Y','y',element.y,'number')}${inputRow('宽度','w',element.w,'number')}${inputRow('高度','h',element.h,'number')}${inputRow('旋转','rotation',element.rotation||0,'number')}${inputRow('透明度','opacity',element.opacity==null?1:element.opacity,'number')}</div>${specific}</form>`;
    const form=document.querySelector('#inspector-form');form.addEventListener('input',event=>{const path=event.target.name;if(!path)return;let value=event.target.type==='number'?Number(event.target.value):event.target.value;if(path.startsWith('style.'))element.style[path.split('.')[1]]=value;else element[path]=value;if(path==='opacity')element.opacity=clamp(value,0,1);markDirty();renderLayers();draw();document.querySelector('#selection-label').textContent=element.name||typeNames[element.type];});
  }
  function renderAll() { draw();renderLayers();renderInspector();const element=selected();document.querySelector('#selection-label').textContent=element?element.name||typeNames[element.type]:'未选择元素';bindingSelect.value=element&&element.binding||''; }
  function syncDocumentControls() { projectName.value=doc.meta.name||'未命名卡片';document.querySelector('#canvas-width').value=doc.canvas.width;document.querySelector('#canvas-height').value=doc.canvas.height;document.querySelector('#canvas-dpi').value=doc.canvas.dpi||300;document.querySelector('#canvas-unit').value=doc.canvas.unit||'mm';document.querySelector('#background-color').value=doc.background.color||'#ffffff';resizeCanvas(); }

  function pointerPosition(event) { const rect=canvas.getBoundingClientRect(),scale=displayScale();return{x:(event.clientX-rect.left)*canvas.width/rect.width/scale,y:(event.clientY-rect.top)*canvas.height/rect.height/scale}; }
  function snapPosition(element,x,y){const threshold=inCurrentUnit(1.2);let sx=x,sy=y;const xAnchors=[0,doc.canvas.width/2,doc.canvas.width],yAnchors=[0,doc.canvas.height/2,doc.canvas.height];doc.elements.forEach(other=>{if(other.id===element.id||other.visible===false)return;xAnchors.push(other.x,other.x+other.w/2,other.x+other.w);yAnchors.push(other.y,other.y+other.h/2,other.y+other.h);});const candidatesX=[[x,0],[x+element.w/2,element.w/2],[x+element.w,element.w]],candidatesY=[[y,0],[y+element.h/2,element.h/2],[y+element.h,element.h]];let bestX=threshold,bestY=threshold;candidatesX.forEach(([position,offset])=>xAnchors.forEach(anchor=>{const distance=Math.abs(anchor-position);if(distance<bestX){bestX=distance;sx=anchor-offset;}}));candidatesY.forEach(([position,offset])=>yAnchors.forEach(anchor=>{const distance=Math.abs(anchor-position);if(distance<bestY){bestY=distance;sy=anchor-offset;}}));return{x:sx,y:sy};}
  function hitElement(point) { for(let i=doc.elements.length-1;i>=0;i--){const element=doc.elements[i];if(element.visible===false)continue;const left=Math.min(element.x,element.x+element.w),right=Math.max(element.x,element.x+element.w),top=Math.min(element.y,element.y+element.h),bottom=Math.max(element.y,element.y+element.h);const pad=element.type==='line'?inCurrentUnit(1.5):0;if(point.x>=left-pad&&point.x<=right+pad&&point.y>=top-pad&&point.y<=bottom+pad)return element;}return null; }
  canvas.addEventListener('pointerdown',event=>{const point=pointerPosition(event);const current=selected();if(current&&!current.locked){const hx=current.x+current.w,hy=current.y+current.h,hitRadius=inCurrentUnit(2);if(Math.abs(point.x-hx)<hitRadius&&Math.abs(point.y-hy)<hitRadius){dragging={mode:'resize',start:point,element:current,original:{w:current.w,h:current.h}};canvas.setPointerCapture(event.pointerId);canvas.classList.add('dragging');return;}}
    const hit=hitElement(point);selectedId=hit&&hit.id;if(hit&&!hit.locked){dragging={mode:'move',start:point,element:hit,original:{x:hit.x,y:hit.y}};canvas.setPointerCapture(event.pointerId);canvas.classList.add('dragging');}renderAll();});
  canvas.addEventListener('pointermove',event=>{if(!dragging)return;const point=pointerPosition(event),dx=point.x-dragging.start.x,dy=point.y-dragging.start.y,element=dragging.element;if(dragging.mode==='move'){const snapped=snapPosition(element,dragging.original.x+dx,dragging.original.y+dy);element.x=clamp(snapped.x,-element.w,doc.canvas.width);element.y=clamp(snapped.y,-Math.max(element.h,inCurrentUnit(1)),doc.canvas.height);}else{element.w=Math.max(element.type==='line'?inCurrentUnit(.1):inCurrentUnit(2),dragging.original.w+dx);element.h=element.type==='line'?dragging.original.h+dy:Math.max(inCurrentUnit(2),dragging.original.h+dy);}markDirty({noHistory:true});draw();});
  canvas.addEventListener('pointerup',event=>{if(!dragging)return;canvas.releasePointerCapture(event.pointerId);canvas.classList.remove('dragging');dragging=null;pushHistory();renderAll();});
  canvas.addEventListener('dblclick',()=>{const element=selected();if(element&&element.type==='text'){const value=prompt('文字内容',element.content||'');if(value!==null){element.content=value;markDirty();renderAll();}}});

  function addElement(type, extra) {
    const count=doc.elements.length,u=inCurrentUnit;const common={id:uid('el'),type,name:typeNames[type],x:u(12+(count%6)*3),y:u(12+(count%6)*3),w:u(34),h:u(16),rotation:0,opacity:1,visible:true,locked:false,style:{}};
    const presets={text:{content:'双击编辑文字',w:u(50),h:u(12),style:{font_family:'Arial',font_size:16,font_weight:'normal',color:'#17232b',align:'left',valign:'middle',line_height:1.2}},rect:{w:u(40),h:u(25),style:{fill:'#e6f2f1',fill_opacity:1,border_color:'#147d80',border_width:u(.6),radius:u(1)}},circle:{w:u(25),h:u(25),style:{fill:'#e6f2f1',fill_opacity:1,border_color:'#147d80',border_width:u(.6)}},line:{w:u(42),h:0,style:{border_color:'#17232b',border_width:u(.8),border_style:'solid'}},qrcode:{w:u(22),h:u(22),content:'{log.callsign}',binding:'log.callsign',style:{fg_color:'#17232b',bg_color:'#ffffff',ecc_level:'M'}},image:{w:u(38),h:u(28),fit:'contain'}};
    const element=Object.assign(common,presets[type]||{},extra||{});if(presets[type]&&presets[type].style)element.style=clone(presets[type].style);doc.elements.push(element);selectedId=element.id;markDirty();renderAll();
  }
  document.querySelectorAll('[data-add]').forEach(button=>button.onclick=()=>{const type=button.dataset.add;if(type==='select'){document.querySelectorAll('[data-add]').forEach(item=>item.classList.toggle('active',item===button));return;}if(type==='image'){document.querySelector('#image-file').click();return;}addElement(type);});
  document.querySelector('#image-file').onchange=event=>{const file=event.target.files[0];if(!file)return;if(file.size>10*1024*1024){HamLogToast.error('图片不能超过 10MB');return;}const reader=new FileReader();reader.onload=()=>{const assetId=uid('asset');doc.assets[assetId]={type:'image',mime:file.type,dataurl:reader.result};addElement('image',{name:file.name,ref:assetId});};reader.readAsDataURL(file);event.target.value='';};
  document.querySelector('#delete-element').onclick=()=>{if(!selectedId)return;doc.elements=doc.elements.filter(element=>element.id!==selectedId);selectedId=null;markDirty();renderAll();};
  document.querySelector('#duplicate').onclick=()=>{const element=selected();if(!element)return;const copy=clone(element);copy.id=uid('el');copy.name=`${copy.name} 副本`;copy.x+=3;copy.y+=3;doc.elements.push(copy);selectedId=copy.id;markDirty();renderAll();};
  function moveLayer(direction){const index=doc.elements.findIndex(element=>element.id===selectedId);if(index<0)return;const next=clamp(index+direction,0,doc.elements.length-1);if(next===index)return;const [element]=doc.elements.splice(index,1);doc.elements.splice(next,0,element);markDirty();renderAll();}
  document.querySelector('#bring-front').onclick=()=>moveLayer(1);document.querySelector('#send-back').onclick=()=>moveLayer(-1);document.querySelector('#undo').onclick=()=>restoreHistory(historyIndex-1);document.querySelector('#redo').onclick=()=>restoreHistory(historyIndex+1);
  document.addEventListener('keydown',event=>{if(event.target.matches('input,textarea,select'))return;if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();restoreHistory(historyIndex+(event.shiftKey?1:-1));}else if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='d'){event.preventDefault();document.querySelector('#duplicate').click();}else if(['Delete','Backspace'].includes(event.key)){event.preventDefault();document.querySelector('#delete-element').click();}});

  ['canvas-width','canvas-height','canvas-dpi'].forEach(id=>document.querySelector(`#${id}`).onchange=event=>{const key=id.replace('canvas-','');const bounds=unitBounds();doc.canvas[key]=clamp(event.target.value,key==='dpi'?72:bounds.min,key==='dpi'?1200:bounds.max);syncDocumentControls();markDirty();draw();});
  document.querySelector('#canvas-unit').onchange=event=>{const previous=doc.canvas.unit,next=event.target.value,dpi=doc.canvas.dpi||300;const convert=value=>mmToUnit(unitToMm(Number(value)||0,previous,dpi),next,dpi);doc.canvas.width=convert(doc.canvas.width);doc.canvas.height=convert(doc.canvas.height);doc.canvas.bleed=convert(doc.canvas.bleed||0);doc.elements.forEach(element=>{element.x=convert(element.x);element.y=convert(element.y);element.w=convert(element.w);element.h=convert(element.h);if(element.style){['border_width','radius'].forEach(key=>{if(element.style[key]!=null)element.style[key]=convert(element.style[key]);});if(element.style.shadow){['x','y','blur'].forEach(key=>{if(element.style.shadow[key]!=null)element.style.shadow[key]=convert(element.style.shadow[key]);});}}});doc.guides.forEach(guide=>{guide.position=convert(guide.position);});doc.canvas.unit=next;syncDocumentControls();markDirty();draw();};
  document.querySelector('#background-color').oninput=event=>{doc.background={type:'color',color:event.target.value};markDirty();draw();};
  document.querySelector('#background-image').onclick=()=>document.querySelector('#background-file').click();
  document.querySelector('#background-file').onchange=event=>{const file=event.target.files[0];if(!file)return;if(file.size>10*1024*1024){HamLogToast.error('背景图片不能超过 10MB');return;}const reader=new FileReader();reader.onload=()=>{const assetId=uid('asset');doc.assets[assetId]={type:'image',mime:file.type,dataurl:reader.result};doc.background={type:'image',ref:assetId,fit:'cover',opacity:1,position:'center'};markDirty();draw();HamLogToast.show('背景图片已应用');};reader.readAsDataURL(file);event.target.value='';};
  document.querySelector('#clear-background').onclick=()=>{doc.background={type:'color',color:document.querySelector('#background-color').value||'#ffffff'};markDirty();draw();};
  projectName.oninput=()=>{doc.meta.name=projectName.value;markDirty();};
  document.querySelector('#apply-binding').onclick=()=>{const element=selected();if(!element){HamLogToast.error('请先选择元素');return;}element.binding=bindingSelect.value||undefined;if(element.binding&&['text','qrcode'].includes(element.type)){const token=`{${element.binding}}`;if(!element.content||/^\{[^}]+\}$/.test(element.content))element.content=token;}markDirty();renderAll();};
  async function bindingData() { const now=new Date();const data={'meta.export_date':now.toISOString().slice(0,10),'meta.export_time':now.toTimeString().slice(0,8),'const.app_name':'HamLog'};const [settingsResult,logsResult]=await Promise.allSettled([HamLogAPI.post('/settings/get_all'),HamLogAPI.post('/log/list',{page:1,page_size:1})]);if(settingsResult.status==='fulfilled'){Object.entries(settingsResult.value||{}).forEach(([key,value])=>data[`station.${key}`]=value);}if(logsResult.status==='fulfilled'&&logsResult.value.items&&logsResult.value.items[0]){const item=logsResult.value.items[0];Object.assign(data,{'log.callsign':item.Callsign||'','log.date':[item.Year,String(item.Month||'').padStart(2,'0'),String(item.Day||'').padStart(2,'0')].join('-'),'log.freq':item.Freq||'','log.mode':item.Mode||'','log.rst':item.Rst_side||item.Rst_self||'','log.qth':item.QTH||'','log.remarks':item.Remarks||'','qsl.rx_date':item.QSL_RX||'','qsl.send_date':item.QSL_SEND||''});}return data;}
  document.querySelector('#preview-binding').onclick=async event=>{if(previewData){previewData=null;event.currentTarget.textContent='预览填充';draw();return;}event.currentTarget.textContent='加载数据...';try{previewData=await bindingData();event.currentTarget.textContent='退出预览';draw();}catch(error){event.currentTarget.textContent='预览填充';HamLogToast.error(error.message);}};

  function updateMeta() { doc.schema_version='1.0';doc.format='hamlog-qsl';doc.meta.name=projectName.value||'未命名卡片';doc.meta.updated_at=new Date().toISOString(); }
  async function save(autosave) { if(autosave&&!dirty)return;updateMeta();try{const data=await HamLogAPI.post(autosave?'/qsl/autosave':'/qsl/save',{id:projectId,name:doc.meta.name,content:doc});projectId=data.id||projectId;dirty=false;statusLabel.textContent=`${autosave?'自动保存':'已保存'} ${new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}`;if(!autosave)HamLogToast.show('QSL 工程已保存');}catch(error){statusLabel.textContent='保存失败';if(!autosave)HamLogToast.error(error.message);}}
  document.querySelector('#save-project').onclick=()=>save(false);
  const autosaveTimer=setInterval(()=>save(true),10000);
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});

  async function showProjects(){if(!projectsDialog.open)projectsDialog.showModal();const target=document.querySelector('#project-list');target.innerHTML='<div class="loading">加载项目...</div>';try{const data=await HamLogAPI.post('/qsl/list');const items=data.items||[];target.innerHTML=items.length?items.map(item=>`<div class="project-row"><div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(dateTime(item.updated_at))}</span></div><div class="project-actions"><button class="button button-secondary" data-open="${escapeHtml(item.id)}">打开</button><button class="button danger-icon" data-remove="${escapeHtml(item.id)}">删除</button></div></div>`).join(''):'<div class="empty-inspector">没有已保存工程。</div>';target.querySelectorAll('[data-open]').forEach(button=>button.onclick=async()=>{try{const data=await HamLogAPI.post('/qsl/load',{id:button.dataset.open});loadDocument(data.content,data.id,data.name);projectsDialog.close();HamLogToast.show('工程已加载');}catch(error){HamLogToast.error(error.message);}});target.querySelectorAll('[data-remove]').forEach(button=>button.onclick=async()=>{if(!confirm('确定删除这个 QSL 工程？'))return;try{await HamLogAPI.post('/qsl/delete',{id:button.dataset.remove});if(projectId===button.dataset.remove)projectId=null;HamLogToast.show('工程已删除');showProjects();}catch(error){HamLogToast.error(error.message);}});}catch(error){target.innerHTML=`<div class="empty-inspector">${escapeHtml(error.message)}</div>`;}}
  function loadDocument(content,id,name){doc=normalizeDocument(content);projectId=id||null;doc.meta.name=name||doc.meta.name||'未命名卡片';selectedId=null;previewData=null;dirty=false;statusLabel.textContent=id?'已加载':'本地工程';syncDocumentControls();resetHistory();renderAll();}
  document.querySelector('#load-project').onclick=showProjects;document.querySelector('#close-projects').onclick=()=>projectsDialog.close();
  document.querySelector('#import-project').onclick=()=>document.querySelector('#project-file').click();document.querySelector('#project-file').onchange=event=>{const file=event.target.files[0];if(!file)return;if(file.size>10*1024*1024){HamLogToast.error('工程文件不能超过 10MB');return;}const reader=new FileReader();reader.onload=()=>{try{const content=JSON.parse(reader.result);if(content.format&&content.format!=='hamlog-qsl')throw new Error('不是 HamLog QSL 工程');loadDocument(content,null,(content.meta&&content.meta.name)||file.name.replace(/\.hamqsl$/i,''));dirty=true;statusLabel.textContent='已导入，尚未保存';HamLogToast.show('工程已导入，可继续编辑');}catch(error){HamLogToast.error(`导入失败：${error.message}`);}};reader.readAsText(file);event.target.value='';};

  async function renderExportCanvas(data) { const dpi=clamp(doc.canvas.dpi||300,72,600),requested=exportScale(dpi);const scale=Math.min(requested,16384/Math.max(1,doc.canvas.width),16384/Math.max(1,doc.canvas.height));const output=document.createElement('canvas');output.width=Math.max(1,Math.round(doc.canvas.width*scale));output.height=Math.max(1,Math.round(doc.canvas.height*scale));const outputContext=output.getContext('2d');drawBackground(outputContext,output.width,output.height,scale);doc.elements.forEach(element=>renderElement(outputContext,element,scale,data||{}));await Promise.all([...imageCache.values()].filter(image=>!image.complete).map(image=>new Promise(resolve=>{image.addEventListener('load',resolve,{once:true});image.addEventListener('error',resolve,{once:true});})));drawBackground(outputContext,output.width,output.height,scale);doc.elements.forEach(element=>renderElement(outputContext,element,scale,data||{}));return output;}
  function safeFilename(extension){return(projectName.value||'qsl-card').replace(/[\\/:*?"<>|]/g,'_')+extension;}
  document.querySelector('#export-menu').onclick=event=>{event.stopPropagation();exportPopover.hidden=!exportPopover.hidden;};document.addEventListener('click',event=>{if(!event.target.closest('#export-popover')&&!event.target.closest('#export-menu'))exportPopover.hidden=true;});
  document.querySelector('#export-private').onclick=()=>{updateMeta();downloadText(JSON.stringify(doc,null,2),safeFilename('.hamqsl'),'application/x-hamlog-qsl+json;charset=utf-8');exportPopover.hidden=true;HamLogToast.show('私有工程已下载');};
  async function exportPublic(format){exportPopover.hidden=true;try{await save(false);if(!projectId)throw new Error('请先保存 QSL 工程');const exported=await HamLogAPI.post('/qsl/export_public',{id:projectId,format,dpi:doc.canvas.dpi||300,data:await bindingData()});await HamLogAPI.download('/qsl/download',{token:exported.token},safeFilename(`.${format}`));HamLogToast.show(format==='pdf'?'PDF 已生成':'PNG 已生成');}catch(error){HamLogToast.error(error.message);}}
  document.querySelector('#export-png').onclick=()=>exportPublic('png');
  document.querySelector('#export-print').onclick=()=>exportPublic('pdf');
  async function loadFields(){try{const data=await HamLogAPI.post('/qsl/data_fields');fields=data.fields&&data.fields.length?data.fields:fallbackFields;}catch(_){fields=fallbackFields;}const groups={};fields.forEach(field=>(groups[field.group||'其他']||(groups[field.group||'其他']=[])).push(field));bindingSelect.innerHTML='<option value="">不绑定</option>'+Object.entries(groups).map(([group,items])=>`<optgroup label="${escapeHtml(group)}">${items.map(field=>`<option value="${escapeHtml(field.key)}">${escapeHtml(field.label)} · ${escapeHtml(field.key)}</option>`).join('')}</optgroup>`).join('');}
  loadDocument(doc,null,doc.meta.name);loadFields();
}());
