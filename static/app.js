
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

const money = value => "£" + Number(value || 0).toLocaleString("en-GB", {maximumFractionDigits:0});
const imageUrl = m => `/static/img/${m.image}`;

async function init(){
  modules = await fetch("/api/modules").then(r => r.json());
  selected = [...presets.entertainer];
  renderCategories();
  renderProducts();
  renderBuild();
}

function renderCategories(){
  document.getElementById("cats").innerHTML = categories.map(([name, icon]) => `
    <div class="cat ${name === activeCategory ? "active" : ""}" onclick="setCategory('${name}')"><i>${icon}</i>${name}</div>
  `).join("");
}

function setCategory(name){
  activeCategory = name;
  renderCategories();
  renderProducts();
}

function visibleProducts(){
  return activeCategory === "All Modules" ? modules : modules.filter(m => m.category === activeCategory);
}

function renderProducts(){
  document.getElementById("productGrid").innerHTML = visibleProducts().map(m => `
    <div class="product" onclick="addModule('${m.id}')">
      <img src="${imageUrl(m)}" alt="${m.name}">
      <div>
        <b>${m.name}</b>
        <strong>${money(m.price)}</strong>
        <small>${m.width ? m.width + "mm" : "Add-on"}</small>
      </div>
    </div>
  `).join("");
}

function addModule(id){
  selected.push(id);
  renderBuild();
}

function removeIndex(index){
  selected.splice(index, 1);
  renderBuild();
}

function clearBuild(){
  selected = [];
  renderBuild();
}

function loadBuild(name){
  selected = [...(presets[name] || [])];
  document.getElementById("builder").scrollIntoView({behavior:"smooth"});
  renderBuild();
}

function unitClass(m){
  let c = "unit ";
  if(m.width >= 1200) c += "xwide ";
  else if(m.width >= 900) c += "wide ";
  if(m.type === "grill") c += "tall ";
  else if(["pizza","kamado"].includes(m.type)) c += "mid ";
  else c += "low ";
  if(m.type === "sink") c += "sink ";
  if(m.type === "fridge") c += "fridge ";
  if(m.type === "corner") c += "corner ";
  if(m.type === "addon") c += "addon ";
  if(m.type === "pergola") c += "pergolaUnit ";
  return c;
}

function renderBuild(){
  const items = selected.map(id => modules.find(m => m.id === id)).filter(Boolean);
  const visualItems = items.filter(m => !["addon","pergola"].includes(m.type));
  const row = document.getElementById("rowBuild");
  document.getElementById("pergola").classList.toggle("show", items.some(m => m.type === "pergola"));

  row.innerHTML = visualItems.length ? "" : `<div class="empty">Choose modules to start your outdoor kitchen</div>`;

  visualItems.forEach((m) => {
    const realIndex = selected.indexOf(m.id);
    const el = document.createElement("div");
    el.className = unitClass(m);
    el.innerHTML = `
      <div class="img" style="background-image:url('${imageUrl(m)}')"></div>
      <div class="door"></div><div class="handle"></div><div class="legs"></div>
      <div class="wheel l"></div><div class="wheel r"></div>
      <div class="label">${m.name}</div>
      ${m.type === "grill" ? '<div class="hood"></div><div class="rack"></div>' : ''}
      ${["pizza","kamado"].includes(m.type) ? '<div class="dome"></div>' : ''}
      ${m.type === "sink" ? '<div class="basin"></div><div class="tap"></div>' : ''}
    `;
    el.onclick = () => removeIndex(realIndex);
    row.appendChild(el);
  });

  const subtotal = items.reduce((s,m) => s + Number(m.price), 0);
  const delivery = items.length ? 450 : 0;
  const vat = Math.round((subtotal + delivery) * 0.2);
  const total = subtotal + delivery + vat;

  document.getElementById("cartItems").innerHTML = items.length ? items.map((m, i) => `
    <div class="cartLine">
      <img src="${imageUrl(m)}" alt="${m.name}">
      <span>${m.name}</span>
      <b>${money(m.price)}</b>
      <span class="remove" onclick="removeIndex(${i})">×</span>
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
  }).then(r => r.json());

  document.getElementById("checkout").style.display = "grid";
  document.getElementById("checkoutSummary").innerHTML = `
    <p><b>Order Ref:</b> ${data.order_ref}</p>
    <p><b>Total:</b> ${money(data.total)} including delivery and VAT estimate.</p>
    <p><b>Approx Width:</b> ${(data.width / 1000).toFixed(2)}m</p>
    <h3>Production BOM</h3>
    ${data.bom.map(x => `<div class="cartLine" style="grid-template-columns:1fr 60px"><span>${x.part}</span><b>${x.qty}</b></div>`).join("")}
  `;
}

function closeCheckout(){
  document.getElementById("checkout").style.display = "none";
}

window.addEventListener("DOMContentLoaded", init);
