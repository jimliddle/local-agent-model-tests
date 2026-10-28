import {appendFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here = path.dirname(fileURLToPath(import.meta.url));
const controller = path.resolve(here, 'control.py');

export default function(pi) {
  const work = process.env.PILOT_WORK;
  const log = (file, value) => appendFileSync(path.join(work,file), JSON.stringify(value)+'\n');
  let requests = 0;
  pi.on('before_provider_request', event => {
    if (++requests > 12) throw new Error('Evaluation request budget exhausted');
    const payload = {...event.payload, temperature:0.6, top_p:0.95,
      seed:Number(process.env.PILOT_SEED), max_tokens:8192};
    if (process.env.BENCH_FLASH === '1') payload.chat_template_kwargs = {enable_thinking:true};
    log('requests.jsonl', {n:requests, model:payload.model,
      reasoning_effort:payload.reasoning_effort, max_tokens:payload.max_tokens,
      temperature:payload.temperature, payload_chars:JSON.stringify(payload).length});
    return payload;
  });
  pi.on('message_end', event => {
    if(event.message.role === 'assistant') log('usage.jsonl', {usage:event.message.usage,
      stopReason:event.message.stopReason, error:event.message.errorMessage});
  });
  const schema = properties => ({type:'object',properties,additionalProperties:false});
  for(const [name,description,parameters] of [
    ['read_source','Read solution.py.',schema({})],
    ['write_source','Replace solution.py with complete corrected functions. Invalidates prior checks.',
      {...schema({source:{type:'string'}}),required:['source']}],
    ['run_check','Run one check: syntax, then unit, then integration. Requires passing predecessors for current source.',
      {...schema({check:{type:'string',enum:['syntax','unit','integration']}}),required:['check']}],
  ]) pi.registerTool({name,label:name,description,parameters,async execute(id,args) {
    const child=spawnSync(process.env.PILOT_PYTHON,[controller,work,name],
      {input:JSON.stringify(args),encoding:'utf8',timeout:18000,maxBuffer:65536});
    const text=child.status===0?child.stdout:JSON.stringify({ok:false,error:'controller failed',status:child.status});
    log('tools.jsonl',{id,name,args,result:JSON.parse(text)});
    return {content:[{type:'text',text}],details:{}};
  }});
}
