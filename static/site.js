
async function calculateQuote(){
  const finish = document.querySelector('input[name="finish"]:checked')?.value || "black";
  const features = [...document.querySelectorAll('.check-grid input:checked')].map(x => x.value);
  const result = await fetch('/api/bespoke-quote', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({finish,features,brief:document.getElementById('brief')?.value || ""})
  }).then(r=>r.json());
  document.getElementById('estimate').textContent = '£' + Number(result.estimate).toLocaleString('en-GB');
}
