const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'..');
function element(){return {style:{},classList:{add(){},remove(){},toggle(){},contains(){return true;}},innerHTML:'',setAttribute(){},remove(){},addEventListener(){}};}
async function authHarness(loginResponses){
 const handlers={}; const elements={'au-email':{value:'synthetic@example.test'},'au-pass':{value:'synthetic-password'},'au-otp':{value:''},'auth-err':element()};
 const appended=[];const calls=[];let loads=0;
 const document={readyState:'loading',body:{...element(),appendChild(e){appended.push(e);}},createElement:element,querySelector(){return null;},getElementById:id=>elements[id]||null,
 addEventListener(type,fn){(handlers[type]??=[]).push(fn);}};
 const window={TFBoot:{mode:'server',ready:Promise.resolve('server'),async api(p,o){calls.push({p,o});
 if(p.endsWith('/tiers'))return {ok:true,data:{tiers:[]}};
 if(p.endsWith('/me'))return {ok:false};
 if(p.endsWith('/login'))return loginResponses.shift();
 return {ok:true,data:{}};},async ensureAppLoaded(){loads++;}}};
 const context={window,document,console,setInterval(){},clearInterval(){},setTimeout(){},localStorage:{getItem(){return null;},setItem(){},removeItem(){}}};
 vm.runInNewContext(fs.readFileSync(path.join(root,'webapp/js/auth.js'),'utf8'),context);
 await handlers.DOMContentLoaded[0]();
 async function click(action){const target={dataset:{act:action},disabled:false};target.closest=s=>s==='[data-act]'?target:null;for(const fn of handlers.click)await fn({target});}
 return {click,elements,appended,calls,window,get loads(){return loads;}};
}
test('MFA challenge never unlocks until a user response is authenticated',async()=>{
 const h=await authHarness([{ok:true,data:{mfa_required:true}},{ok:true,data:{user:{email:'synthetic@example.test',name:'Reviewer',tier:'beta'}}}]);
 await h.click('login');assert.equal(h.loads,0);assert.match(h.appended[0].innerHTML,/Verify your login/);
 h.elements['au-otp'].value='123456';await h.click('verify-mfa');assert.equal(h.loads,1);
 assert.equal(h.calls.filter(x=>x.p.endsWith('/login'))[1].o.body.otp,'123456');
});
test('Invalid second factor stays on challenge without loading private data',async()=>{
 const h=await authHarness([{ok:true,data:{mfa_required:true}},{ok:false,data:{detail:'Invalid code'}}]);
 await h.click('login');h.elements['au-otp'].value='000000';await h.click('verify-mfa');
 assert.equal(h.loads,0);assert.equal(h.elements['auth-err'].textContent,'Invalid code');
});
test('Recovery code uses recovery field and cancel clears pending credentials',async()=>{
 const h=await authHarness([{ok:true,data:{mfa_required:true}},{ok:false,data:{detail:'Used code'}}]);
 await h.click('login');h.elements['au-otp'].value='aaaa-bbbb';await h.click('verify-mfa');
 assert.equal(h.calls.filter(x=>x.p.endsWith('/login'))[1].o.body.recovery,'aaaa-bbbb');
 await h.click('to-login');await h.click('verify-mfa');assert.equal(h.calls.filter(x=>x.p.endsWith('/login')).length,2);
});
test('Unauthorized data load rejects, and a later successful attempt can retry',async()=>{
 let authorized=false;
 const window={TF:{init(){}}};
 const document={cookie:'',createElement:()=>({}),body:{appendChild(s){s.onload();}}};
 const fetch=async p=>({ok:p==='/api/healthz'||authorized,status:authorized?200:401,json:async()=>({fixture:true})});
 vm.runInNewContext(fs.readFileSync(path.join(root,'webapp/js/boot.js'),'utf8'),{window,document,fetch,console});
 await window.TFBoot.ready;
 await assert.rejects(window.TFBoot.ensureAppLoaded(),/unavailable/);
 authorized=true;await window.TFBoot.ensureAppLoaded();
});
