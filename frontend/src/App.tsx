import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { ArrowUpRight, BookOpen, CalendarDays, ChartNoAxesCombined, ChevronDown, CircleHelp, Database, LayoutDashboard, Menu, Orbit, PanelLeftClose, ShieldCheck, Sparkles, Store, TrendingUp, X } from 'lucide-react';
import { OverviewPage, ForecastPage, StoresPage } from './DashboardPages';
import { LoadState, useApi, date } from './components';
import type { Meta, Page } from './types';
const ModelsPage=lazy(()=>import('./SciencePages').then(m=>({default:m.ModelsPage})));
const ExplainPage=lazy(()=>import('./SciencePages').then(m=>({default:m.ExplainPage})));
const QualityPage=lazy(()=>import('./SciencePages').then(m=>({default:m.QualityPage})));
const AUTHOR_URL='https://github.com/kvvraju24';
const navigation=[{id:'overview',label:'Executive Overview',icon:LayoutDashboard},{id:'forecast',label:'6-Week Forecasting',icon:TrendingUp},{id:'stores',label:'Store Analytics',icon:Store},{id:'models',label:'Model Comparison',icon:ChartNoAxesCombined},{id:'explain',label:'Explainable AI',icon:Sparkles},{id:'quality',label:'Data Quality',icon:ShieldCheck}] as const;
const pageCopy:Record<Page,{title:string;description:string;eyebrow:string}>={overview:{title:'Executive overview',description:'The big picture. Every store, every sale, every opportunity.',eyebrow:'YOUR BUSINESS AT A GLANCE'},forecast:{title:'A clearer view of what’s next.',description:'Plan ahead with daily, store-level revenue predictions.',eyebrow:'6-WEEK FORECASTING'},stores:{title:'Every store has a story.',description:'Explore performance, compare stores, and understand promotion patterns.',eyebrow:'STORE ANALYTICS'},models:{title:'Let the results speak.',description:'Three forecasting approaches. One shared, unseen evaluation period.',eyebrow:'MODEL COMPARISON'},explain:{title:'Beyond the black box.',description:'See the factors shaping your revenue forecasts.',eyebrow:'EXPLAINABLE AI'},quality:{title:'Confidence starts with the data.',description:'Source coverage, missing values, and the health of the forecasting pipeline.',eyebrow:'DATA QUALITY & MONITORING'}};
function initialPage():Page {const hash=window.location.hash.slice(1);return navigation.some(n=>n.id===hash)?hash as Page:'overview';}
export default function App(){
  const metaState=useApi<Meta>('/api/meta');
  const [page,setPage]=useState<Page>(initialPage),[store,setStore]=useState(0),[days,setDays]=useState(42),[mobileOpen,setMobileOpen]=useState(false),[help,setHelp]=useState(false);
  useEffect(()=>{const listener=()=>setPage(initialPage());window.addEventListener('hashchange',listener);return()=>window.removeEventListener('hashchange',listener);},[]);
  const modalRef=useRef<HTMLElement>(null);
  useEffect(()=>{
    if(!help) return;
    const previous=document.activeElement as HTMLElement|null;
    const onKey=(e:KeyboardEvent)=>{
      if(e.key==='Escape'){setHelp(false);return;}
      if(e.key!=='Tab')return;
      const nodes=modalRef.current?.querySelectorAll<HTMLElement>('button, a[href], input, select, [tabindex="0"]');
      if(!nodes?.length)return;
      const first=nodes[0],last=nodes[nodes.length-1];
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
      else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
    };
    document.addEventListener('keydown',onKey);
    return()=>{document.removeEventListener('keydown',onKey);previous?.focus();};
  },[help]);
  const meta=metaState.data;
  const needsForecast=page==='forecast'||page==='explain';
  const effectiveStore=needsForecast&&store&&!meta?.stores.find(s=>s.id===store)?.forecast?0:store;
  const navigate=(p:Page)=>{window.location.hash=p;setPage(p);setMobileOpen(false);window.scrollTo({top:0,behavior:'instant'});};
  const copy=pageCopy[page];
  return <div className="app-shell">
    {mobileOpen&&<button className="sidebar-overlay" aria-label="Close navigation" onClick={()=>setMobileOpen(false)}/>}
    <aside className={`sidebar ${mobileOpen?'open':''}`}><a href="#overview" className="brand" onClick={()=>navigate('overview')}><span className="brand-mark"><Sparkles size={22} strokeWidth={1.8}/></span><div>northstar<span>SALES INTELLIGENCE</span></div></a><button className="mobile-close icon-button" aria-label="Close navigation" onClick={()=>setMobileOpen(false)}><PanelLeftClose size={19}/></button>
      <div className="workspace-switch"><span className="workspace-logo">R</span><div>Rossmann Retail<small>Public dataset · 2013–2015</small></div><ChevronDown size={14}/></div>
      <div className="nav-label">WORKSPACE</div><nav aria-label="Main navigation">{navigation.map(n=><button key={n.id} onClick={()=>navigate(n.id)} className={page===n.id?'active':''} aria-current={page===n.id?'page':undefined}><n.icon size={18}/><span>{n.label}</span>{n.id==='forecast'&&<span className="nav-new">ML</span>}{page===n.id&&<span className="active-dot"/>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="dataset-card"><div className="dataset-card-heading"><Database size={16}/><span>Built on real data</span><span className="mini-dot"/></div><p>1M+ observations.<br/>1,115 stores. One clear view.</p><div className="stack-tags"><span>React</span><span>FastAPI</span><span>XGBoost</span></div></div><button className="sidebar-help" onClick={()=>setHelp(true)}><BookOpen size={16}/>Project & methodology<ArrowUpRight size={14}/></button><div className="sidebar-footer"><span className="avatar">KV</span><div>Koneti Vishnuvardhan Raju<small><a href={AUTHOR_URL} target="_blank" rel="noreferrer">Built by · GitHub ↗</a></small></div><span className="version">v1.1</span></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumbs"><button className="mobile-menu icon-button" aria-label="Open navigation" onClick={()=>setMobileOpen(true)}><Menu size={20}/></button><span>Workspace</span><span className="slash">/</span><b>{navigation.find(n=>n.id===page)?.label}</b></div><div className="topbar-right"><span className="snapshot-indicator"><span className="mini-dot"/>Historical snapshot</span><span className="topbar-divider"/><button className="icon-button" aria-label="Project information" onClick={()=>setHelp(true)}><CircleHelp size={18}/></button><a className="avatar small" href={AUTHOR_URL} target="_blank" rel="noreferrer" aria-label="Author on GitHub">KV</a></div></header>
      <main><div className="page-header"><div><div className="eyebrow page-eyebrow"><span/> {copy.eyebrow}</div><h1>{copy.title}</h1><p>{copy.description}</p></div>{page==='overview'&&<button className="button" onClick={()=>navigate('forecast')}><TrendingUp size={15}/>View forecast<ArrowUpRight size={14}/></button>}</div>
        <div className="filter-row"><div className="scope-title"><span className="mini-dot"/><span>{page==='quality'?'Dataset-wide audit':effectiveStore?`Store ${effectiveStore}`:'Network overview'}</span><span className="scope-divider"/><span>{meta?`${page==='forecast'||page==='explain'?meta.forecast_store_count:meta.store_count} stores in dataset scope`:'Loading dataset…'}</span></div><div className="filter-controls">{page!=='quality'&&<label className="filter-select"><Store size={14}/><select aria-label="Select store" value={effectiveStore} onChange={e=>setStore(Number(e.target.value))}><option value={0}>All stores</option>{meta?.stores.filter(s=>!needsForecast||s.forecast).map(s=><option key={s.id} value={s.id}>Store {s.id} · Format {s.type}</option>)}</select></label>}{page==='overview'||page==='stores'?<label className="filter-select"><CalendarDays size={14}/><select aria-label="Historical period" value={days} onChange={e=>setDays(Number(e.target.value))}><option value={28}>Last 28 days</option><option value={42}>Last 42 days</option><option value={90}>Last 90 days</option><option value={180}>Last 180 days</option></select></label>:<span className="date-pill"><CalendarDays size={14}/>{page==='forecast'||page==='explain'?'Aug – Sep 2015':page==='models'?'Jun – Jul 2015':'Jan 2013 – Jul 2015'}</span>}</div></div>
        {!meta?<LoadState {...metaState}/>:<Suspense fallback={<LoadState loading error={null} retry={()=>{}}/>}>{page==='overview'?<OverviewPage store={store} days={days} navigate={navigate} selectStore={setStore}/>:page==='forecast'?<ForecastPage store={effectiveStore}/>:page==='stores'?<StoresPage store={store} days={days} navigate={navigate} selectStore={setStore}/>:page==='models'?<ModelsPage store={store} meta={meta}/>:page==='explain'?<ExplainPage store={effectiveStore}/>:<QualityPage/>}</Suspense>}
        <footer className="main-footer"><span><Orbit size={13}/>Northstar · Sales & revenue forecasting</span><span>Revenue in dataset sales units<span className="footer-dot">·</span>Actuals through {meta?date(meta.history_end,true):'31 Jul 2015'}</span></footer>
      </main>
    </div>
    {help&&<div className="modal-backdrop" onClick={()=>setHelp(false)}><section ref={modalRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="project-title" onClick={e=>e.stopPropagation()} onKeyDown={e=>{if(e.key==='Escape')setHelp(false);}}><button className="modal-close icon-button" aria-label="Close project information" autoFocus onClick={()=>setHelp(false)}><X size={20}/></button><span className="brand-mark"><Sparkles size={24}/></span><div className="eyebrow">THE PROJECT</div><h2 id="project-title">From sales history<br/>to clearer decisions.</h2><p>Northstar is a full-stack data science project built on the Rossmann Store Sales dataset. Every chart, forecast, and model metric comes from the source data.</p><p className="small-print">Designed and built by <a href={AUTHOR_URL} target="_blank" rel="noreferrer">Koneti Vishnuvardhan Raju</a>.</p><div className="modal-stack"><span>React + TypeScript</span><span>FastAPI + Python</span><span>XGBoost + Ridge</span><span>Tree SHAP</span></div><div className="context-list"><div><span>Historical observations</span><strong>Jan 2013 – Jul 2015</strong></div><div><span>Validation</span><strong>Final 42 observed days</strong></div><div><span>Forecast scope</span><strong>856 stores · Aug – Sep 2015</strong></div></div><p className="small-print">The source has store sales, customer counts, promotions, holidays, and store metadata. It has no SKU sales, product prices, or competitor sales. It is a historical demonstration with no live feed.</p><div className="modal-actions"><a className="button lime" href="/docs" target="_blank" rel="noreferrer">Explore API<ArrowUpRight size={14}/></a><a className="button" href={AUTHOR_URL} target="_blank" rel="noreferrer">Author on GitHub<ArrowUpRight size={14}/></a><button className="button" onClick={()=>{setHelp(false);navigate('models');}}>Model evaluation<ArrowRightIcon/></button></div></section></div>}
  </div>;
}
function ArrowRightIcon(){return <ArrowUpRight size={14}/>;}
