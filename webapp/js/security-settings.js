/* Account security UI. Secrets/recovery codes exist only in the open dialog. */
"use strict";
(() => {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function openSecurity() {
    if (document.getElementById('account-security-dialog')) return;
    const dialog = document.createElement('dialog');
    dialog.id = 'account-security-dialog'; dialog.className = 'auth-card security-dialog';
    dialog.setAttribute('aria-label', 'Account security');
    document.body.appendChild(dialog);
    dialog.addEventListener('close', () => dialog.remove());
    dialog.showModal();
    const api = async (path, body) => {
      const r = await window.TFBoot.api(path, body === undefined ? {} : {method:'POST',body});
      if (!r.ok) throw new Error((r.data && r.data.detail) || 'Request failed. Please retry.');
      return r.data;
    };
    const error = (e) => { const el=dialog.querySelector('[role="alert"]'); if(el) el.textContent=e.message; };
    function frame(html) {
      dialog.innerHTML = `<h2 class="auth-h">Account security</h2>${html}<p role="alert" class="auth-p"></p><button class="auth-btn auth-btn-ghost" id="security-close">Close</button>`;
      dialog.querySelector('#security-close').onclick=()=>dialog.close();
    }
    function action(id, fn) {
      dialog.querySelector('#'+id).onclick=async (event)=>{
        const button=event.currentTarget; if(button.disabled)return;button.disabled=true;
        try {await fn();} catch(e){error(e);} finally{button.disabled=false;}
      };
    }
    async function overview() {
      const {user}=await api('/api/auth/me');
      const {sessions}=await api('/api/auth/sessions');
      frame(`<p class="auth-p">Authenticator: ${user.mfa_enabled?'enabled':'not enabled'}</p>`+
        (user.mfa_enabled ? `<label class="auth-p" for="security-code">Current authenticator code</label><input class="auth-in" id="security-code" autocomplete="one-time-code" inputmode="numeric"><button class="auth-btn" id="disable-mfa">Disable authenticator</button>` :
        `<button class="auth-btn" id="setup-mfa">Set up authenticator</button>`)+
        `<h3>Active sessions</h3><ul>${sessions.map(s=>`<li>${escape(s.device || 'Device')}${s.current?' (this device)':''}${s.current?'':` <button type="button" data-revoke="${escape(s.sid)}">Revoke</button>`}</li>`).join('')}</ul>`);
      if(user.mfa_enabled) action('disable-mfa',async()=>{await api('/api/auth/mfa/disable',{code:dialog.querySelector('#security-code').value.trim()});await overview();});
      else action('setup-mfa',setup);
      dialog.querySelectorAll('[data-revoke]').forEach(button=>button.onclick=async()=>{
        button.disabled=true;try {await api('/api/auth/sessions/revoke',{sid:button.dataset.revoke});await overview();}catch(e){error(e);button.disabled=false;}
      });
    }
    async function setup() {
      const enrollment=await api('/api/auth/mfa/setup',{});
      frame(`<p class="auth-p">Add this setup key to your authenticator. Save the recovery codes in a safe place; they are shown only during setup.</p>
        <label class="auth-p" for="setup-key">Setup key</label><input id="setup-key" class="auth-in" readonly value="${escape(enrollment.secret)}">
        <pre class="security-recovery">${enrollment.recovery_codes.map(escape).join('\n')}</pre>
        <label class="auth-p" for="security-code">Code from your authenticator</label><input class="auth-in" id="security-code" autocomplete="one-time-code" inputmode="numeric">
        <button class="auth-btn" id="enable-mfa">Verify and enable</button>`);
      action('enable-mfa',async()=>{await api('/api/auth/mfa/enable',{code:dialog.querySelector('#security-code').value.trim()});await overview();});
    }
    frame('<p class="auth-p">Loading account security…</p>');
    try {
      if (!(window.TFBoot && window.TFBoot.mode==='server')) throw new Error('Account security requires the hosted application.');
      await overview();
    } catch(e){error(e);}
  }
  document.addEventListener('click',event=>{if(event.target.closest('#securityBtn'))openSecurity();});
})();
