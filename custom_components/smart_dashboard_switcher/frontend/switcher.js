/* Smart Dashboard Switcher v0.2.1 – render Lovelace cards without an iframe.
 * Uses Home Assistant's frontend card helpers and Lovelace config websocket API.
 */
class SmartDashboardSwitcherPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:'open'});
    this._hass = null;
    this._panel = null;
    this._active = null;
    this._pending = null;
    this._pendingSince = 0;
    this._timer = null;
    this._generation = 0;
    this._cards = [];
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;height:100%;min-height:0;background:var(--primary-background-color,#111);color:var(--primary-text-color,#fff)}
      #content{width:100%;height:100%;overflow:auto;box-sizing:border-box}
      #content.panel{display:block}
      #content.panel > *{display:block;width:100%;box-sizing:border-box}
      #content.normal{max-width:1200px;margin:auto;padding:12px}
      #content.normal > *{display:block;margin-bottom:12px}
      #message{padding:24px;font:15px sans-serif;white-space:pre-wrap}
      #status{position:fixed;right:12px;bottom:12px;background:#222e;color:#fff;border-radius:8px;padding:7px 11px;font:13px sans-serif;z-index:5;pointer-events:none}
      #status[hidden]{display:none}
    </style><div id="content"><div id="message">Lade Dashboard …</div></div><div id="status" hidden></div>`;
    this._content = this.shadowRoot.getElementById('content');
    this._status = this.shadowRoot.getElementById('status');
  }
  set hass(value) {
    this._hass = value;
    for (const card of this._cards) card.hass = value;
    this._evaluate();
  }
  set panel(value) {this._panel = value;this._evaluate();}
  connectedCallback() {
    if (!this._timer) this._timer = setInterval(() => this._evaluate(), 1000);
    this._evaluate();
  }
  disconnectedCallback() {clearInterval(this._timer);this._timer = null;this._generation++;}
  _showStatus(text) {this._status.textContent=text;this._status.hidden=false;}
  _hideStatus() {this._status.hidden=true;}
  _error(text) {this._content.replaceChildren();const msg=document.createElement('div');msg.id='message';msg.textContent=text;this._content.append(msg);}
  _evaluate() {
    const cfg=this._panel?.config;
    if (!cfg || !this._hass || !this.isConnected) return;
    const state=this._hass.states[cfg.entity]?.state;
    if (state!=='on' && state!=='off') {
      this._pending=null;
      if (!this._active) this._showStatus('Warte auf gültigen Ventilzustand');
      return;
    }
    const path=state==='on'?cfg.on_path:cfg.off_path;
    const own=cfg.panel_url||'info-display';
    const first='/'+(path||'').split('?')[0].split('/').filter(Boolean)[0];
    // Never render ourselves (panel or our own dashboard) -> endless nesting.
    if (typeof path!=='string' || !path.startsWith('/') || path.startsWith('//') || first==='/'+own || first==='/dashboard-'+own) {
      this._error('Ungültiger Dashboard-Pfad. Bitte Integration konfigurieren.');return;
    }
    if (path===this._active) {this._pending=null;this._hideStatus();return;}
    if (this._pending!==path) {this._pending=path;this._pendingSince=Date.now();}
    const delay=Math.max(0,Number(state==='on'?cfg.delay_on:cfg.delay_off)||0)*1000;
    const remaining=delay-(Date.now()-this._pendingSince);
    if (remaining>0 && this._active) {this._showStatus('Ansicht wechselt in '+Math.ceil(remaining/1000)+' s');return;}
    this._pending=null;
    this._active=path;
    this._hideStatus();
    this._renderPath(path);
  }
  async _renderPath(path) {
    const generation=++this._generation;
    this._cards=[];
    this._error('Lade '+path+' …');
    try {
      // /dashboard-name/view-path: dashboard-name is the Lovelace URL path.
      // /lovelace/view-path: default dashboard (url_path omitted).
      const parts=new URL(path,location.origin).pathname.split('/').filter(Boolean);
      if (!parts.length) throw Error('Dashboard-Pfad fehlt');
      const dashboard=parts[0];
      const viewPath=parts[1] || '0';
      const request={type:'lovelace/config'};
      if (dashboard!=='lovelace') request.url_path=dashboard;
      const config=await this._hass.callWS(request);
      if (generation!==this._generation || !this.isConnected) return;
      const views=config.views || [];
      const view=views.find(v=>v.path===viewPath) || (/^\d+$/.test(viewPath)?views[Number(viewPath)]:undefined);
      if (!view) throw Error('Ansicht '+viewPath+' nicht gefunden in '+dashboard);
      const helpers=await window.loadCardHelpers();
      if (generation!==this._generation || !this.isConnected) return;
      // Lovelace supports cards in classic views and sections in newer views.
      // A custom card may also be supplied directly as a view configuration.
      let configs=Array.isArray(view.cards) ? view.cards : [];
      if (!configs.length && Array.isArray(view.sections)) {
        configs=view.sections.flatMap(section => {
          const sectionCards=Array.isArray(section.cards) ? section.cards : [];
          if (!sectionCards.length) return [];
          // Keep each section together instead of losing its grouping.
          return [{type:'vertical-stack',cards:sectionCards}];
        });
      }
      if (!configs.length && typeof view.type==='string' && view.type.startsWith('custom:')) {
        configs=[view];
      }
      const cards=[];
      for (const cardConfig of configs) {
        const card=helpers.createCardElement(cardConfig);
        card.hass=this._hass;
        cards.push(card);
      }
      if (generation!==this._generation || !this.isConnected) return;
      this._content.className=view.type==='panel'?'panel':'normal';
      this._content.replaceChildren(...cards);
      this._cards=cards;
      if (!cards.length) this._error('Keine Karten gefunden. Prüfe, ob die Solar-Karte unter cards: oder sections: in der richtigen Ansicht liegt ('+path+').');
    } catch(err) {
      if (generation!==this._generation || !this.isConnected) return;
      this._error('Dashboard konnte nicht geladen werden:\n'+String(err?.message||err)+'\n\nPrüfe Dashboard-URL, Zugriffsrechte und Frontend-Ressourcen.\nNeuer Versuch in 15 s …');
      // Retry later (e.g. HA still starting); otherwise the error would stay until the valve changes.
      setTimeout(() => {
        if (generation===this._generation && this._active===path) {this._active=null;this._evaluate();}
      }, 15000);
    }
  }
}
if (!customElements.get('smart-dashboard-switcher-panel')) customElements.define('smart-dashboard-switcher-panel',SmartDashboardSwitcherPanel);


// Lovelace bridge: use a real Home Assistant dashboard as the selectable start page.
// The panel remains registered (even if hidden), supplying per-instance settings.
class SmartDashboardSwitcherCard extends SmartDashboardSwitcherPanel {
  constructor() { super(); this._cardConfig = null; }
  setConfig(config) {
    if (!config || typeof config.panel_url !== 'string' || !/^[a-z0-9][a-z0-9_-]*$/.test(config.panel_url)) {
      throw new Error('panel_url muss gesetzt sein, z.B. info-display');
    }
    this._cardConfig = config;
    this._updatePanelConfig();
  }
  set hass(value) {
    this._hass = value;
    for (const card of this._cards) card.hass = value;
    this._updatePanelConfig();
    this._evaluate();
  }
  get hass() { return this._hass; }
  _updatePanelConfig() {
    if (!this._hass || !this._cardConfig) return;
    const path = this._cardConfig.panel_url;
    const registered = this._hass.panels?.[path];
    if (registered?.config) {
      this._panel = {config: registered.config};
    } else {
      // Some HA versions don't expose hidden custom panels to the Lovelace context.
      // In that case, explicit card parameters can provide a reliable fallback.
      const c = this._cardConfig;
      if (c.entity && c.on_path && c.off_path) {
        this._panel = {config: {
          entity: c.entity, on_path: c.on_path, off_path: c.off_path,
          delay_on: c.delay_on ?? 30, delay_off: c.delay_off ?? 120,
          panel_url: path,
        }};
      } else {
        this._panel = null;
        this._error('Switcher-Konfiguration nicht verfügbar. Bitte entity, on_path und off_path in der Karte ergänzen.');
      }
    }
  }
  getCardSize() { return 12; }
}
if (!customElements.get('smart-dashboard-switcher-card')) customElements.define('smart-dashboard-switcher-card', SmartDashboardSwitcherCard);
window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === 'smart-dashboard-switcher-card')) {
  window.customCards.push({type:'smart-dashboard-switcher-card', name:'Smart Dashboard Switcher', description:'Dashboard-Umschalter als auswählbares Lovelace-Dashboard'});
}
