import { useEffect, useState, type ReactNode } from 'react';
import { ArrowDownRight, ArrowUpRight, AlertCircle, RefreshCw, Info } from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Line, ComposedChart } from 'recharts';

export const compact = (n:number) => new Intl.NumberFormat('en', {notation:'compact',maximumFractionDigits:2}).format(n);
export const number = (n:number) => new Intl.NumberFormat('en', {maximumFractionDigits:0}).format(n);
export const pct = (n:number|null, digits=1) => n === null ? '—' : `${(n*100).toFixed(digits)}%`;
export const date = (v:string, year=false) => new Date(v.slice(0,10)+'T12:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short',...(year?{year:'numeric'}:{})});
export const colors = {lime:'#bcf57b',teal:'#70daca',purple:'#a496ee',blue:'#7daefb',muted:'#637184'};
export const axis = {axisLine:false,tickLine:false,tick:{fill:'#8491a3',fontSize:11},minTickGap:28};
export const tooltipStyle = {background:'#19232e',border:'1px solid #344252',borderRadius:10,fontSize:12,color:'#eef3f8',boxShadow:'0 12px 30px #0005'};

export function useApi<T>(url:string|null) {
  const [state,setState] = useState<{data:T|null;error:string|null;loading:boolean}>({data:null,error:null,loading:true});
  const [retry,setRetry] = useState(0);
  useEffect(()=>{
    if(!url) return;
    const controller = new AbortController();
    setState({data:null,error:null,loading:true});
    fetch(url,{signal:controller.signal}).then(async r=>{
      if(!r.ok) {const e=await r.json().catch(()=>({detail:'Could not load data'}));throw new Error(typeof e.detail==='string'?e.detail:'Please check the selected filters.');}
      return r.json() as Promise<T>;
    }).then(data=>setState({data,error:null,loading:false})).catch(e=>{if(e.name!=='AbortError')setState({data:null,error:e.message,loading:false});});
    return ()=>controller.abort();
  },[url,retry]);
  return {...state,retry:()=>setRetry(x=>x+1)};
}
export function LoadState({loading,error,retry}:{loading:boolean;error:string|null;retry:()=>void}){
  if(error)return <div className="empty-state" role="alert"><AlertCircle size={28}/><h2>We couldn’t load this view</h2><p>{error}</p><button className="button" onClick={retry}><RefreshCw size={15}/>Try again</button></div>;
  if(loading)return <div className="skeleton-grid" aria-label="Loading dashboard" aria-busy="true">{[0,1,2,3,4,5].map(i=><div key={i} className="skeleton"/>)}</div>;
  return null;
}
export function Panel({title,subtitle,action,children,className=''}:{title:string;subtitle?:string;action?:ReactNode;children:ReactNode;className?:string}){
  return <section className={`panel ${className}`}><div className="panel-heading"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</div>{children}</section>;
}
export function Change({value,label='vs. previous period'}:{value:number|null;label?:string}){
  return <span className={`change ${value!==null&&value<0?'negative':''}`}>{value!==null&&value<0?<ArrowDownRight size={13}/>:<ArrowUpRight size={13}/>}<b>{value===null?'—':`${value>=0?'+':''}${pct(value)}`}</b><span>{label}</span></span>;
}
export function Sparkline({values,color=colors.lime}:{values:number[];color?:string}){
  const max=Math.max(...values,1),min=Math.min(...values,0),range=max-min||1;
  const points=values.map((v,i)=>`${i/(Math.max(values.length-1,1))*112},${36-(v-min)/range*32}`).join(' ');
  return <svg className="sparkline" viewBox="0 0 114 40" aria-hidden="true"><polyline points={points} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}
export function Kpi({label,value,note,icon,values,color,change}:{label:string;value:string;note:ReactNode;icon:ReactNode;values?:number[];color?:string;change?:number|null}){
  return <div className="kpi"><div className="kpi-label">{label}<span>{icon}</span></div><div className="kpi-number">{value}{values&&<Sparkline values={values} color={color}/>}</div><div className="kpi-note">{change!==undefined?<Change value={change}/>:note}</div></div>;
}
export function Note({children}:{children:ReactNode}){return <div className="note"><Info size={15}/><span>{children}</span></div>;}
export function RevenueChart({data,primary='value',secondary,color=colors.lime,height=275,primaryName='Revenue',secondaryName='Previous period'}:{data:object[];primary?:string;secondary?:string;color?:string;height?:number;primaryName?:string;secondaryName?:string}){
  return <div style={{height,width:'100%'}} role="img" aria-label={`${primaryName} over time`}><ResponsiveContainer width="100%" height="100%"><ComposedChart data={data} margin={{top:15,right:15,bottom:0,left:0}}><defs><linearGradient id={`fill-${primary}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={0.2}/><stop offset="95%" stopColor={color} stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#ffffff09" vertical={false}/><XAxis dataKey="date" {...axis} tickFormatter={v=>date(String(v))} dy={8}/><YAxis {...axis} tickFormatter={compact} width={52}/><Tooltip contentStyle={tooltipStyle} labelFormatter={v=>date(String(v),true)} formatter={(v,name)=>[number(Number(v)),name]}/>{secondary&&<Line type="monotone" dataKey={secondary} name={secondaryName} stroke="#607388" strokeWidth={1.5} strokeDasharray="5 5" dot={false}/>}<Area type="monotone" dataKey={primary} name={primaryName} stroke={color} strokeWidth={2.2} fill={`url(#fill-${primary})`} activeDot={{r:4,stroke:'#101720',strokeWidth:3}}/></ComposedChart></ResponsiveContainer></div>;
}
export function MiniChart({data}:{data:object[]}){return <div style={{height:110,width:'100%'}}><ResponsiveContainer><AreaChart data={data}><defs><linearGradient id="miniFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={colors.lime} stopOpacity={0.28}/><stop offset="100%" stopColor={colors.lime} stopOpacity={0}/></linearGradient></defs><Area dataKey="prediction" type="monotone" stroke={colors.lime} fill="url(#miniFill)" strokeWidth={2}/><Tooltip contentStyle={tooltipStyle} formatter={v=>number(Number(v))}/></AreaChart></ResponsiveContainer></div>;}
