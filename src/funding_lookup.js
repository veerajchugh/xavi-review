// model query: funding (last round size/date, total raised) for current employers of this week's candidates, for the recent-raise and buzzy-startup rules
const IDS=inputs.ids;
const out={};
for (const ch of chunk(IDS,100)) {
  const r=await callTool('company_search',{filters:in_('crustdata_company_id',ch),limit:100,fields:['crustdata_company_id','basic_info.name','funding.total_investment_usd','funding.last_round_amount_usd','funding.last_fundraise_date','funding.last_round_type']});
  if(!r.ok) return {err:r.message,out};
  for (const c of r.data.companies) out[c.crustdata_company_id]={n:c.basic_info&&c.basic_info.name,t:c.funding&&c.funding.total_investment_usd,l:c.funding&&c.funding.last_round_amount_usd,d:c.funding&&c.funding.last_fundraise_date,r:c.funding&&c.funding.last_round_type};
  checkpoint(out);
}
return {n:Object.keys(out).length,out};