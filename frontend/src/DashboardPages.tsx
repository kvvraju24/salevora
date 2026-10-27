import { useState } from 'react';
import { ArrowRight, ArrowUpRight, Banknote, CalendarDays, Download, Store, TrendingUp, Users, Search, ChevronLeft, ChevronRight, SlidersHorizontal } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, ComposedChart } from 'recharts';
import { useApi, LoadState, Panel, Kpi, Note, Change, RevenueChart, MiniChart, compact, number, pct, date, colors, axis, tooltipStyle } from './components';
import type { Overview, Forecast, StoreData, Page, Model, Series } from './types';

type Props={store:number;days:number;navigate:(p:Page)=>void;selectStore:(s:number)=>void};
function groupWeeks(data:Series[]) {
  const out:Series[]=[];
  for(let i=0;i<data.length;i+=7)out.push({date:data[i].date,value:data.slice(i,i+7).reduce((s,r)=>s+r.value,0),previous:data.slice(i,i+7).reduce((s,r)=>s+(r.previous||0),0)});
  return out;
}
export function OverviewPage({store,days,navigate,selectStore}:Props){
  const state=useApi<Overview>(`/api/overview?store=${store}&days=${days}`);
  const future=useApi<Forecast>(`/api/forecast?store=${store}&horizon=42`);
  const [frequency,setFrequency]=useState<'Daily'|'Weekly'>('Daily');
  const [rank,setRank]=useState<'Top performers'|'Lower revenue'>('Top performers');
  if(!state.data)return <LoadState {...state}/>;
  const d=state.data,f=future.data;
  const ranking=rank==='Top performers'?d.top_stores:d.low_stores;
  return <div className="page-enter">
    <div className="kpi-grid">
      <Kpi label="Total revenue" value={compact(d.revenue)} note="" icon={<Banknote size={17}/>} values={d.series.map(x=>x.value)} change={d.growth}/>
      <Kpi label="Average daily revenue" value={compact(d.daily_average)} note={<><span className="mini-dot"/>Across {days} calendar days</>} icon={<TrendingUp size={17}/>} values={groupWeeks(d.series).map(x=>x.value/7)} color={colors.teal}/>
      <Kpi label="Customer visits" value={compact(d.customers)} note="Recorded visits · not unique customers" icon={<Users size={17}/>} values={d.series.map(x=>x.customers||0)} color={colors.purple}/>
      <Kpi label="Stores in view" value={number(d.stores)} note={<><span className="mini-dot"/>{pct(d.open_rate)} of store-days open</>} icon={<Store size={17}/>}/>
    </div>
    <div className="overview-main">
      <Panel title="Revenue performance" subtitle={`${date(d.start)} – ${date(d.end,true)} · sales units`} action={<div className="segmented">{(['Daily','Weekly'] as const).map(v=><button key={v} className={v===frequency?'active':''} onClick={()=>setFrequency(v)}>{v}</button>)}</div>}>
        <div className="chart-legend"><span><i style={{background:colors.lime}}/>Current period</span><span><i className="dashed"/>Previous {days} days</span></div>
        <RevenueChart data={frequency==='Daily'?d.series:groupWeeks(d.series)} secondary="previous" height={282}/>
      </Panel>
      <section className="forecast-preview"><div className="forecast-preview-top"><span className="eyebrow"><span className="mini-dot"/>LOOKING AHEAD</span><TrendingUp size={19}/></div><h2>Your next 6 weeks,<br/>in focus.</h2><p>Revenue forecast from XGBoost</p>
        {f?<><div className="forecast-big">{compact(f.total)}<span>sales units</span></div><Change value={f.change} label="vs. previous 42 days"/><MiniChart data={f.series}/><div className="preview-dates"><span>{date(f.start)}</span><span>{date(f.end,true)}</span></div><div className="preview-meta"><span>{number(f.stores)} stores</span><span>42-day horizon</span></div></>:<p className="forecast-unavailable">{future.loading?'Loading model forecast…':future.error||'Forecast unavailable'}</p>}
        <button className="button lime full" onClick={()=>navigate('forecast')}>Explore forecast<ArrowRight size={16}/></button>
      </section>
    </div>
    <div className="two-col overview-bottom">
      <Panel title="Store leaderboard" subtitle="Ranked by revenue in the selected period" action={<select aria-label="Leaderboard ranking" className="quiet-select" value={rank} onChange={e=>setRank(e.target.value as typeof rank)}><option>Top performers</option><option>Lower revenue</option></select>}>
        <div className="leaderboard">{ranking.map((s,i)=><button className="leader-row" key={s.Store} onClick={()=>{selectStore(s.Store);navigate('stores');}}><span className="rank">{String(i+1).padStart(2,'0')}</span><span className="store-avatar"><Store size={15}/></span><span className="leader-name">Store {s.Store}<small>Format {s.StoreType.toUpperCase()}</small></span><span className="leader-track"><span style={{width:`${Math.max(4,s.revenue/Math.max(...ranking.map(r=>r.revenue))*100)}%`}}/></span><strong>{compact(s.revenue)}</strong><ArrowUpRight size={15}/></button>)}</div>
        <button className="text-button panel-bottom" onClick={()=>navigate('stores')}>View all stores <ArrowRight size={14}/></button>
      </Panel>
      <Panel title="The weekly rhythm" subtitle="Average revenue per store-day" action={<span className="badge neutral">{days}-day view</span>}>
        <div className="weekday-chart"><ResponsiveContainer width="100%" height={220}><BarChart data={d.weekday} margin={{top:20,right:4,left:-4,bottom:0}}><CartesianGrid stroke="#ffffff09" vertical={false}/><XAxis dataKey="DayOfWeek" {...axis} tickFormatter={v=>['','Mon','Tue','Wed','Thu','Fri','Sat','Sun'][Number(v)]}/><YAxis {...axis} tickFormatter={compact} width={45}/><Tooltip contentStyle={tooltipStyle} cursor={{fill:'#ffffff04'}} labelFormatter={v=>['','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][Number(v)]} formatter={v=>[number(Number(v)),'Average revenue']}/><Bar dataKey="revenue" radius={[5,5,0,0]} maxBarSize={34}>{d.weekday.map(r=><Cell key={r.DayOfWeek} fill={r.revenue===Math.max(...d.weekday.map(v=>v.revenue))?colors.lime:'#344b43'}/>)}</Bar></BarChart></ResponsiveContainer></div>
        <div className="panel-insight"><span className="mini-dot"/>{pct(d.promo_share,0)} of revenue came from promotion days.</div>
      </Panel>
    </div>
    {d.observed_rows!==d.previous_rows&&<Note>Growth compares observed revenue totals: {number(d.observed_rows)} current store-days versus {number(d.previous_rows)} in the previous period. Missing records can affect this comparison; totals are not coverage-adjusted.</Note>}
  </div>;
}

export function ForecastPage({store}:{store:number}){
  const [model,setModel]=useState<Model>('XGBoost'),[horizon,setHorizon]=useState(42),[view,setView]=useState<'Daily'|'Cumulative'>('Daily');
  const state=useApi<Forecast>(`/api/forecast?store=${store}&horizon=${horizon}&model=${model}`);
  return <div className="page-enter"><div className="control-bar"><div className="control-group"><label>Forecast model<select aria-label="Forecast model" value={model} onChange={e=>setModel(e.target.value as Model)}><option>XGBoost</option><option>Ridge</option><option>Baseline</option></select></label><label>Horizon<select aria-label="Forecast horizon" value={horizon} onChange={e=>setHorizon(Number(e.target.value))}><option value="14">2 weeks · 14 days</option><option value="28">4 weeks · 28 days</option><option value="42">6 weeks · 42 days</option></select></label></div><a className="button" href={`/api/forecast/export?store=${store}&model=${model}&horizon=${horizon}`} download><Download size={15}/>Export forecast</a></div>
    {!state.data?<LoadState {...state}/>:<ForecastContent d={state.data} view={view} setView={setView} store={store}/>}
  </div>;
}
function ForecastContent({d,view,setView,store}:{d:Forecast;view:'Daily'|'Cumulative';setView:(v:'Daily'|'Cumulative')=>void;store:number}){
  return <><div className="kpi-grid"><Kpi label="Predicted revenue" value={compact(d.total)} note="" change={d.change} icon={<Banknote size={17}/>} values={d.series.map(x=>x.prediction)}/><Kpi label="Daily average" value={compact(d.daily_average)} note="Including scheduled closures" icon={<TrendingUp size={17}/>}/><Kpi label="Forecast coverage" value={number(d.stores)} note={store?`Store ${store} · scheduled store-days`:'Of 1,115 historical stores'} icon={<Store size={17}/>}/><Kpi label="Prediction horizon" value={`${d.horizon} days`} note={`${date(d.start)} – ${date(d.end,true)}`} icon={<CalendarDays size={17}/>}/></div>
    <Panel title={view==='Daily'?'Daily revenue forecast':'Cumulative revenue forecast'} subtitle={`${d.model} · fitted through 31 Jul 2015 · sales units`} action={<div className="segmented">{(['Daily','Cumulative'] as const).map(v=><button className={view===v?'active':''} key={v} onClick={()=>setView(v)}>{v}</button>)}</div>}>
      <div className="chart-legend"><span><i style={{background:colors.lime}}/>{d.model} prediction</span>{store>0&&view==='Daily'&&<span><i style={{background:'#5c7343'}}/>Indicative historical error range</span>}</div>
      <div style={{height:330,width:'100%'}}><ResponsiveContainer><ComposedChart data={d.series} margin={{top:15,left:0,right:20,bottom:5}}><CartesianGrid stroke="#ffffff09" vertical={false}/><XAxis {...axis} dataKey="date" tickFormatter={v=>date(String(v))}/><YAxis {...axis} tickFormatter={compact} width={60}/><Tooltip contentStyle={tooltipStyle} labelFormatter={v=>date(String(v),true)} formatter={(v,n)=>[Array.isArray(v)?v.map(x=>number(Number(x))).join(' – '):number(Number(v)),n]}/>{store>0&&view==='Daily'&&<Area isAnimationActive={false} dataKey="range" name="Error range" stroke="none" fill={colors.lime} fillOpacity={0.1}/>}<Area isAnimationActive={false} key={view} dataKey={view==='Daily'?'prediction':'cumulative'} name={view==='Daily'?'Predicted revenue':'Cumulative revenue'} type="monotone" stroke={colors.lime} fill={colors.lime} fillOpacity={0.06} strokeWidth={2.3}/></ComposedChart></ResponsiveContainer></div>
    </Panel>
    <div className="two-col section-gap"><Panel title="Week by week" subtitle="Revenue across the forecast horizon"><div className="weekly-cards">{d.weekly.map(w=><div className="week-row" key={w.week}><span>Week {w.week}</span><div className="horizontal-track"><span style={{width:`${w.prediction/Math.max(...d.weekly.map(x=>x.prediction))*100}%`}}/></div><b>{compact(w.prediction)}</b></div>)}</div></Panel><Panel title="Forecast context" subtitle="What goes into these predictions"><div className="context-list"><div><span>Comparison period</span><strong>Previous {d.horizon} days, same stores</strong></div><div><span>Model inputs</span><strong>Calendar, promotions & store history</strong></div><div><span>Closed store-days</span><strong>Predicted sales set to zero</strong></div><div><span>Actual future sales</span><strong>Not provided in this dataset</strong></div></div></Panel></div>
    <Note>{store?d.range_note:'Select an individual store to inspect its indicative error range. Network totals do not include a confidence band because store errors can be correlated.'} The supplied schedule has 48 days; this view uses up to the first 42.</Note>
  </>;
}

export function StoresPage({store,days,selectStore}:Props){
  const state=useApi<StoreData>(`/api/stores?store=${store}&days=${days}`);
  const [search,setSearch]=useState(''),[format,setFormat]=useState('all'),[sort,setSort]=useState('revenue'),[page,setPage]=useState(0);
  if(!state.data)return <LoadState {...state}/>;
  const d=state.data;
  const filtered=d.stores.filter(s=>(!store||s.Store===store)&&String(s.Store).includes(search)&&(format==='all'||s.StoreType===format)).sort((a,b)=>sort==='revenue'?b.revenue-a.revenue:sort==='growth'?(b.growth??-Infinity)-(a.growth??-Infinity):a.Store-b.Store);
  const currentPage=Math.min(page,Math.max(0,Math.ceil(filtered.length/10)-1));
  const promo=d.promo.find(x=>x.Promo===1),normal=d.promo.find(x=>x.Promo===0);
  return <div className="page-enter"><div className="two-col"><Panel title={store?`Store ${store} · revenue history`:'Network revenue history'} subtitle={`Last ${days} days · sales units`}><RevenueChart data={d.history} height={230}/></Panel><Panel title="Promotion & revenue" subtitle="Average revenue on open store-days"><div className="promo-comparison"><div><span className="eyebrow">WITH PROMOTION</span><strong>{compact(promo?.average||0)}</strong><small>{number(promo?.observations||0)} observations</small></div><div><span className="eyebrow">WITHOUT PROMOTION</span><strong>{compact(normal?.average||0)}</strong><small>{number(normal?.observations||0)} observations</small></div></div><div className="promo-bars"><div style={{width:'100%'}}/><div style={{width:`${Math.min(100,(normal?.average||0)/(promo?.average||1)*100)}%`}}/></div><p className="inline-explanation">{d.promo_note}</p></Panel></div>
    <Panel title="Explore your stores" subtitle={`${number(filtered.length)} stores · ${days}-day performance`} className="section-gap" action={<SlidersHorizontal size={17} className="muted"/>}>
      <div className="table-controls"><div className="search-input"><Search size={16}/><input aria-label="Search store ID" placeholder="Search store ID…" value={search} onChange={e=>{setSearch(e.target.value);setPage(0);}}/></div><select aria-label="Filter store format" value={format} onChange={e=>{setFormat(e.target.value);setPage(0);}}><option value="all">All store formats</option>{['a','b','c','d'].map(t=><option key={t} value={t}>Format {t.toUpperCase()}</option>)}</select><select aria-label="Sort stores" value={sort} onChange={e=>{setSort(e.target.value);setPage(0);}}><option value="revenue">Highest revenue</option><option value="growth">Highest growth</option><option value="id">Store number</option></select>{store>0&&<button className="text-button" onClick={()=>selectStore(0)}>Clear store filter</button>}</div>
      <div className="table-scroll"><table><thead><tr><th>Store</th><th>Format</th><th>Revenue</th><th>Growth</th><th>Customer visits</th><th>Revenue / open day</th><th>Forecast</th></tr></thead><tbody>{filtered.slice(currentPage*10,currentPage*10+10).map(s=><tr key={s.Store}><td><button className="store-link" onClick={()=>selectStore(s.Store)}><span className="store-avatar"><Store size={14}/></span>Store {s.Store}</button></td><td><span className="format-chip">{s.StoreType.toUpperCase()}</span></td><td className="strong">{number(s.revenue)}</td><td><span className={s.growth!==null&&s.growth<0?'negative-text':'positive-text'}>{s.growth!==null&&s.growth>0?'+':''}{pct(s.growth)}</span></td><td>{number(s.customers)}</td><td>{number(s.revenue_per_open_day||0)}</td><td><span className={`badge ${s.forecast_available?'':'neutral'}`}>{s.forecast_available?'Available':'History only'}</span></td></tr>)}</tbody></table>{filtered.length===0&&<div className="empty-table">No stores match these filters.</div>}</div>
      <div className="pagination"><span>{filtered.length?`${currentPage*10+1}–${Math.min((currentPage+1)*10,filtered.length)} of ${number(filtered.length)} stores`:'0 stores'}</span><div><button aria-label="Previous page" disabled={currentPage===0} onClick={()=>setPage(currentPage-1)}><ChevronLeft size={16}/></button><span>Page {currentPage+1}</span><button aria-label="Next page" disabled={(currentPage+1)*10>=filtered.length} onClick={()=>setPage(currentPage+1)}><ChevronRight size={16}/></button></div></div>
    </Panel><Note>Growth compares the previous {days} calendar days. Store formats and assortment codes are anonymized dataset categories. Customer counts are visits, not distinct people.</Note>
  </div>;
}
