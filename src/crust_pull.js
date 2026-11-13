// model query: pull founding engineers (2-8 yoe, not current founders) for weekly xavi review queue
const C = inputs.country, extra = inputs.extra || [];
const conds = [
  eq('basic_profile.location.country', C),
  field('experience.employment_details.title', '(.)', 'founding engineer'),
  field('years_of_experience_raw', '=>', 2),
  field('years_of_experience_raw', '=<', 8),
  field('experience.employment_details.current.title', '(!)', 'founder'),
  field('experience.employment_details.current.title', '(!)', 'CEO'),
  field('experience.employment_details.current.title', '(!)', 'CTO'),
  field('experience.employment_details.current.seniority_level', 'not_in', ['CXO','Owner / Partner']),
];
// standing rules: drop robotics / pure-EE current titles and people now at hot startups (they won't leave)
for (const t of (inputs.exclude_titles || [])) conds.push(field('experience.employment_details.current.title', '(!)', t));
if ((inputs.exclude_companies || []).length) conds.push(field('experience.employment_details.current.name', 'not_in', inputs.exclude_companies));
for (const e of extra) conds.push(e[0] === 'OR' ? or_(...e[1].map(x => field(x[0], x[1], x[2]))) : field(e[0], e[1], e[2]));
const slimJob = j => ({t:j.title,c:j.name,s:(j.start_date||'').slice(0,7),e:(j.end_date||'').slice(0,7)||null,hc:j.company_headcount_latest,ind:(j.company_industries||[])[0]||null,web:j.company_website,sen:j.seniority_level});
const out = []; let cursor = inputs.cursor || null; let total = null;
for (let i = 0; i < (inputs.pages||2); i++) {
  const q = {filters: and_(...conds), limit: 100, fields: ['crustdata_person_id','basic_profile','social_handles','experience.employment_details.current','experience.employment_details.past']};
  if (inputs.exclude) q.post_processing = {exclude_profiles: inputs.exclude};
  if (cursor) q.cursor = cursor;
  const r = await callTool('person_search', q);
  if (!r.ok) return {err: r, out, cursor};
  total = r.data.total_count;
  for (const p of r.data.profiles) {
    const b = p.basic_profile||{}, s = p.social_handles||{}, x = (p.experience||{}).employment_details||{};
    out.push({id:p.crustdata_person_id,name:b.name,head:b.headline,title:b.current_title,loc:(b.location||{}).raw,pic:b.profile_picture_permalink,
      url:((s.professional_network_identifier)||{}).profile_url,gh:((s.dev_platform_identifier)||{}).profile_url,tw:((s.twitter_identifier)||{}).slug,
      cur:(x.current||[]).map(slimJob),past:(x.past||[]).slice(0,8).map(slimJob)});
  }
  cursor = r.data.next_cursor; checkpoint({out,cursor});
  if (!cursor) break;
}
return {total, cursor, n: out.length, out};
