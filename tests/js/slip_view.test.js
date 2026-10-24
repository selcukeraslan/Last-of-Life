const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const C=require('../../static/slip-calc.js');

test('Kuponum renders the final score and does not erase it when today live feed is empty', async()=>{
  const node={innerHTML:''};
  const item={id:'old',market:'1',home:'A',away:'B',leagueName:'Lig',kickoff:'2020-01-01T18:00Z',p:.7,iddaaOdds:1.5,claudeOdds:1.4};
  let storage=JSON.stringify({items:[item],stake:100});
  const window={SlipCalc:C,addEventListener(){}};
  const state={live:new Map()};
  const document={hidden:false,activeElement:null,addEventListener(){},querySelectorAll(){return []},
    querySelector(s){return s==='#slip'?node:s==='#tab-slip'?{classList:{contains:()=>false}}:null}};
  const context=vm.createContext({window,state,document,URLSearchParams,Date,Map,Set,console,
    localStorage:{getItem:()=>storage,setItem:(_,value)=>{storage=value}},
    setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,
    fetch:async(url)=>{
      assert.match(url,/^\/api\/results\?/);
      return {ok:true,json:async()=>({matches:{old:{id:'old',state:'post',home_goals:2,away_goals:1,minute:'MS'}}})};
    }});
  vm.runInContext(fs.readFileSync('static/slip.js','utf8'),context);
  await window.Slip.render();
  assert.match(node.innerHTML,/Bitti/);
  assert.match(node.innerHTML,/2–1/);
  assert.match(node.innerHTML,/Tuttu/);
  assert.doesNotMatch(node.innerHTML,/>başladı</);
  window.Slip.updateLive();
  assert.match(node.innerHTML,/2–1/);
  assert.equal(JSON.parse(storage).items[0].result.state,'post');
});
