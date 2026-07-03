
let modules = [];
let selected = [];
let activeCategory = "All Modules";

const categories = [
  ["All Modules","▦"],["BBQ Grills","▥"],["Storage","▣"],["Fridges","▤"],["Sinks & Taps","♨"],
  ["Cooking","▧"],["Accessories","╱"],["Extras","▱"],["Structures","⌂"],["Decor & Lighting","☼"]
];

const presets = {
  entertainer:["charcoal_bbq","drawer_unit","double_door","fridge","sink","pizza_oven","bar","led","utensil_rail"],
  family:["double_door","fridge","sink","charcoal_bbq","drawer_unit","bin_drawer","led"],
  chef:["argentine_grill","drawer_unit","side_burner","kamado","pizza_oven","bar","pergola","led"],
  ultimate:["corner","fridge","sink","double_door","charcoal_bbq","drawer_unit","pizza_oven","bar","pergola","led","utensil_rail"]
};

const money = v => "£" + Number(v || 0).toLocaleString("en-GB",{maximumFractionDigits:0});
const img = m => `/static/img/${m.image}`;

async function init(){
  modules = await fetch("/api/modules").then(r=>r.json());
  selected = [...presets.entertainer];
  renderCategories();
  renderProducts();
  renderBuild();
}

function renderCategories(){
  document.getElementById("catbar").innerHTML = categories.map(([name,icon]) => `
    <div class="cat ${activeCategory===name?'active':''}" onclick="setCategory('${name}')"><span>${icon}</span>${name}</div>
  `).join("");
}
function setCategory(name){ activeCategory=name; renderCategories(); renderProducts(); }
function productList(){ return activeCategory === "All Modules" ? modules : modules.filter(m=>m.category===activeCategory); }
function renderProducts(){
  document.getElementById("productGrid").innerHTML = productList().map(m=>`
    <div class="product" onclick="addModule('${m.id}')">
      <img src="${img(m)}" alt="${m.name}">
      <b>${m.name}</b>
      <strong>${money(m.price)}</strong>
    </div>
  `).join("");
}
function addModule(id){ selected.push(id); renderBuild(); }
function removeIndex(i){ selected.splice(i,1); renderBuild(); }
function clearBuild(){ selected=[]; renderBuild(); }
function loadBuild(name){ selected=[...(presets[name] || [])]; renderBuild(); }

function moduleClass(m){
  let cls = m.height || "low";
  if(m.id.includes("sink")) cls += " sink";
  if(m.id.includes("fridge")) cls += " fridge";
  if(m.id.includes("corner")) cls += " corner";
  return cls;
}

function renderBuild(){
  const items = selected.map(id=>modules.find(m=>m.id===id)).filter(Boolean);
  const visualItems = items.filter(m=>!["addon","structure"].includes(m.height));
  const row = document.getElementById("buildRow");
  document.getElementById("pergola").classList.toggle("show", items.some(m=>m.height==="structure"));
  row.innerHTML = visualItems.length ? "" : `<div class="empty">Choose a module to start your Invictus outdoor kitchen</div>`;

  visualItems.forEach((m)=>{
    const originalIndex = selected.indexOf(m.id);
    const unit = document.createElement("div");
    unit.className = "moduleVisual " + moduleClass(m);
    unit.style.width = Math.max(90, Number(m.width || 600)/6) + "px";
    unit.innerHTML = `
      <div class="productOverlay" style="background-image:url('${img(m)}')"></div>
      <div class="door"></div><div class="handle"></div><div class="legs"></div>
      <div class="wheel l"></div><div class="wheel r"></div><div class="label">${m.name}</div>
      ${m.height==="high" ? '<div class="hood"></div><div class="rack"></div>' : ''}
      ${m.height==="medium" ? '<div class="dome"></div>' : ''}
      ${m.id.includes("sink") ? '<div class="basin"></div><div class="tap"></div>' : ''}
    `;
    unit.onclick = () => removeIndex(originalIndex);
    row.appendChild(unit);
  });

  const subtotal = items.reduce((s,m)=>s+Number(m.price),0);
  const delivery = items.length ? 450 : 0;
  const vat = Math.round((subtotal + delivery)*0.2);
  const total = subtotal + delivery + vat;

  document.getElementById("cartItems").innerHTML = items.length ? items.map((m,i)=>`
    <div class="cartLine">
      <img src="${img(m)}" alt="${m.name}">
      <span>${m.name}</span><b>${money(m.price)}</b><span class="remove" onclick="removeIndex(${i})">×</span>
    </div>
  `).join("") : `<p class="muted">Your design is empty.</p>`;

  document.getElementById("subtotal").textContent = money(subtotal);
  document.getElementById("delivery").textContent = money(delivery);
  document.getElementById("vat").textContent = money(vat);
  document.getElementById("total").textContent = money(total);
}

async function checkout(){
  const data = await fetch("/api/checkout", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({selected})
  }).then(r=>r.json());

  document.getElementById("checkout").style.display = "grid";
  document.getElementById("checkoutSummary").innerHTML = `
    <p><b>Order Ref:</b> ${data.order_ref}</p>
    <p><b>Total:</b> ${money(data.total)} including delivery and VAT estimate.</p>
    <p><b>Approx Width:</b> ${(data.width/1000).toFixed(2)}m</p>
    <h3>Production BOM</h3>
    ${data.bom.map(x=>`<div class="cartLine" style="grid-template-columns:1fr 60px"><span>${x.part}</span><b>${x.qty}</b></div>`).join("")}
  `;
}
function closeCheckout(){ document.getElementById("checkout").style.display="none"; }

window.addEventListener("DOMContentLoaded", init);
