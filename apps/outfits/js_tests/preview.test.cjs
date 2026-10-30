const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const scriptPath = path.resolve(__dirname, '../static/outfits/js/chat.js');
const code = fs.readFileSync(scriptPath, 'utf8');

function fixture(responses = [], {workspace = true} = {}) {
    let nextId = 0;
    const timers = new Map();
    const calls = [];
    const globalHandlers = {};
    function element(initial = {}) {
        return Object.assign({hidden:false, dataset:{}, handlers:{}, attributes:{}, value:'', focused:false,
            addEventListener(name, callback) { (this.handlers[name] ||= []).push(callback); },
            setAttribute(name, value) { this.attributes[name] = value; },
            removeAttribute(name) { delete this.attributes[name]; },
            contains(target) { return target === this; }, focus() { this.focused = true; },
        }, initial);
    }
    const button = element();
    const firstLink = element();
    const elements = Object.fromEntries(['chat-history-toggle','chat-history-panel','chat-messages','chat-form','chat-prompt','chat-errors','chat-status'].map(id=>[id,element()]));
    elements['chat-history-panel'].hidden = true;
    elements['chat-history-panel'].querySelector = () => firstLink;
    elements['chat-form'].querySelector = () => button;
    elements['chat-messages'].scrollHeight = 200;
    const startForm = element();
    startForm.querySelectorAll = () => [button];
    const image = {src:'http://localhost/wardrobe/photos/1/', alt:'Kaos'};
    const work = {dataset:{previewStatusUrl:'/outfits/conversations/id/preview/?version=1'}, querySelector:()=>image};
    const assigned = [];
    const context = {
        URL, AbortController, CustomEvent: class {constructor(type){this.type=type;}},
        FormData: class {},
        window:{location:{origin:'http://localhost',href:'http://localhost/outfits/conversations/id/',assign:url=>assigned.push(url)},addEventListener:(name,fn)=>{globalHandlers[name]=fn;}},
        document:{getElementById:id=>elements[id],querySelectorAll:()=>[startForm],querySelector:()=>workspace?work:null,
            addEventListener:(name,fn)=>{globalHandlers[name]=fn;}},
        fetch:async(url,options)=>{calls.push({url,options});const result=responses.shift();if(result instanceof Error)throw result;return result||{ok:true,json:async()=>({preview_status:'not_generated'})};},
        setTimeout:(fn,delay)=>{const id=++nextId;timers.set(id,{fn,delay});return id;},
        clearTimeout:id=>timers.delete(id),
    };
    vm.runInNewContext(code, context, {filename:scriptPath});
    return {elements,image,button,calls,timers,globalHandlers,startForm,firstLink,assigned,
        async poll(){const task=[...timers].find(([,v])=>v.delay===0||v.delay===3000);if(!task)return false;timers.delete(task[0]);await task[1].fn();return true;},
        async submit(value='best'){elements['chat-prompt'].value=value;await elements['chat-form'].handlers.submit[0]({preventDefault(){}});},
    };
}
const response = data => ({ok:true,json:async()=>data});

test('queued/running poll with GET only, ready uses same-origin private image', async()=>{
    const f=fixture([response({preview_status:'queued'}),response({preview_status:'running'}),response({preview_status:'ready',preview_url:'/outfits/conversations/id/preview/image/?version=1',preview_label:'Ilustrasi AI'})]);
    await f.poll();assert.match(f.elements['chat-status'].textContent,/antrean/);
    await f.poll();assert.match(f.elements['chat-status'].textContent,/dibuat/);
    await f.poll();assert.match(f.image.src,/\/preview\/image\//);
    assert.equal(f.image.alt,'Ilustrasi AI');assert.equal(f.calls.length,3);
    assert.ok(f.calls.every(c=>c.options.method===undefined&&c.options.credentials==='same-origin'));
    assert.equal(await f.poll(),false);
    f.image.onerror();assert.equal(f.image.src,'http://localhost/wardrobe/photos/1/');
    assert.match(f.elements['chat-status'].textContent,/belum tersedia/);
});

test('terminal statuses retain garment photos and do not enqueue or poll again', async()=>{
    for(const state of ['stale','failed_or_unknown','limit_reached','disabled','not_generated','unexpected']){
        const f=fixture([response({preview_status:state})]);await f.poll();
        assert.equal(f.image.src,'http://localhost/wardrobe/photos/1/');assert.equal(f.elements['chat-status'].hidden,false);
        assert.equal(await f.poll(),false);assert.equal(f.calls.length,1);
    }
});

test('external preview URLs are rejected',async()=>{
    const f=fixture([response({preview_status:'ready',preview_url:'https://external.example/image'})]);await f.poll();
    assert.equal(f.image.src,'http://localhost/wardrobe/photos/1/');
});

test('HTTP failures and timeouts never cause generate retries',async()=>{
    for(const result of [{ok:false},new Error('timeout')]){
        const f=fixture([result]);await f.poll();assert.equal(f.calls.length,1);assert.equal(await f.poll(),false);
        assert.equal(f.elements['chat-status'].hidden,false);
    }
});

test('polling is bounded and refresh starts with a status read only',async()=>{
    const states=Array.from({length:100},()=>response({preview_status:'queued'}));
    const f=fixture(states);for(let i=0;i<100;i++)await f.poll();
    assert.equal(f.calls.length,100);assert.equal(await f.poll(),false);
    assert.match(f.elements['chat-status'].textContent,/generate tidak diulang/);
    const refreshed=fixture([response({preview_status:'running'})]);await refreshed.poll();
    assert.equal(refreshed.calls[0].options.method,undefined);
});

test('pagehide stops polling and late status updates',async()=>{
    const f=fixture();f.globalHandlers.pagehide();await f.poll();assert.equal(f.calls.length,0);
    let release;
    const delayed={ok:true,json:()=>new Promise(resolve=>{release=resolve;})};
    const g=fixture([delayed]);const pending=g.poll();await new Promise(resolve=>setImmediate(resolve));g.globalHandlers.pagehide();
    release({preview_status:'ready',preview_url:'/other',preview_label:'late'});await pending;
    assert.equal(g.image.alt,'Kaos');
});

test('missing workspace produces no status request',async()=>{const f=fixture([],{workspace:false});await f.poll();assert.equal(f.calls.length,0);});

test('history menu opens, closes with Escape/outside pointer/focus, and restores focus',()=>{
    const f=fixture();const toggle=f.elements['chat-history-toggle'];const panel=f.elements['chat-history-panel'];
    const click=()=>toggle.handlers.click[0]();
    click();assert.equal(panel.hidden,false);assert.equal(f.firstLink.focused,true);
    f.globalHandlers.keydown({key:'Escape',preventDefault(){}});assert.equal(panel.hidden,true);assert.equal(toggle.focused,true);
    click();click();assert.equal(panel.hidden,true);
    click();f.globalHandlers.pointerdown({target:{}});assert.equal(panel.hidden,true);
    click();f.globalHandlers.focusin({target:{}});assert.equal(panel.hidden,true);
});

test('landing submit guard blocks duplicate submission and resets on pageshow',()=>{
    const f=fixture();let prevented=false;
    f.startForm.handlers.submit[0]({preventDefault(){prevented=true;}});
    assert.equal(f.button.disabled,true);
    f.startForm.handlers.submit[0]({preventDefault(){prevented=true;}});assert.equal(prevented,true);
    f.globalHandlers.pageshow();assert.equal(f.button.disabled,false);
});

test('empty message does not send and valid match stops old polling',async()=>{
    const f=fixture([response({ok:true,url:'/outfits/conversations/new/'})]);
    await f.submit('  ');assert.equal(f.calls.length,0);assert.equal(f.elements['chat-prompt'].focused,true);
    await f.submit('acak');assert.equal(f.calls[0].options.method,'POST');assert.equal(f.assigned.length,1);
    await f.poll();assert.equal(f.calls.length,1);
});

test('match error, unsafe navigation, and lost response keep key and enable retry',async()=>{
    for(const result of [{ok:false,json:async()=>({errors:{prompt:[{message:'Ditolak'}]}})},response({ok:true,url:'https://external.example'}),new Error('timeout')]){
        const f=fixture([result]);await f.submit();assert.equal(f.button.disabled,false);
        assert.equal(f.elements['chat-errors'].hidden,false);assert.equal(f.assigned.length,0);
    }
});
