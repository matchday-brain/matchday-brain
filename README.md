
<!doctype html>
<html>
<head>
  <title>Invictus Outdoor Living</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
<div class="page">
  <header class="header">
    <div class="brand">
      <img src="{{ url_for('static', filename='img/invictus-logo.png') }}" alt="Invictus">
      <div class="brandText">INVICTUS<span>OUTDOOR LIVING</span></div>
    </div>
    <nav class="nav">
      <a href="#builder" class="active">Build your kitchen</a>
      <a href="#presets">Gallery</a>
      <a href="#builder">Products</a>
      <a>About us</a>
      <a>Finance</a>
      <a>Contact</a>
    </nav>
    <div class="headerActions">
      <div class="ha"><b>♙</b>Account</div>
      <div class="ha"><b>♡</b>Saved</div>
      <div class="ha"><b>🛒</b>Basket</div>
    </div>
  </header>

  <section class="hero">
    <div class="heroCopy">
      <div class="kicker">Precision engineered outdoor kitchens</div>
      <h1>Build your perfect <span>outdoor living</span> space</h1>
      <p>Choose a grill, add modular cupboards, sinks, fridges, bars, pizza ovens, lighting and structures. Every design updates live with price, dimensions and a production bill of materials.</p>
      <div class="heroButtons">
        <a class="btn btnPrimary" href="#builder">Start building</a>
        <a class="btn btnGhost" href="#presets">View popular builds</a>
      </div>
    </div>
    <aside class="heroPanel">
      <h3>Your factory-ready configurator</h3>
      <div class="stat"><span>Live design</span><b>Visual</b></div>
      <div class="stat"><span>Pricing</span><b>Instant</b></div>
      <div class="stat"><span>Manufacturing</span><b>BOM</b></div>
      <div class="stat"><span>Brand</span><b>Invictus</b></div>
    </aside>
  </section>

  <section id="builder" class="builder">
    <aside class="left">
      <div id="cats" class="cats"></div>
      <div class="parts">
        <h2>Choose modules</h2>
        <p class="muted">Select product sections to grow the kitchen. Click a built module to remove it.</p>
        <div id="productGrid" class="productGrid"></div>
      </div>
    </aside>

    <main class="stage">
      <div class="stageTop">
        <div><h2>Design your outdoor living space</h2><p>Build it. Visualise it. Price it.</p></div>
        <div class="toggles"><button class="active">☀ Day</button><button>☾ Night</button><button>⬡ 360° view</button></div>
      </div>
      <div class="design">
        <div id="pergola" class="pergola"></div>
        <div id="rowBuild" class="rowBuild"></div>
      </div>
      <div class="dock">
        <button><b>↶</b>Undo</button>
        <button><b>↷</b>Redo</button>
        <button onclick="clearBuild()"><b>⌫</b>Clear</button>
        <button><b>▣</b>Save</button>
        <button class="btnPrimary btn" onclick="checkout()">Get quote</button>
      </div>
    </main>

    <aside class="cart">
      <h2>Your Design</h2>
      <div id="cartItems"></div>
      <div class="totals">
        <div class="r"><span>Subtotal</span><b id="subtotal">£0</b></div>
        <div class="r"><span>Delivery</span><b id="delivery">£0</b></div>
        <div class="r"><span>VAT (20%)</span><b id="vat">£0</b></div>
        <div class="big"><span>Total</span><span id="total">£0</span></div>
      </div>
      <button class="btn btnPrimary full" onclick="checkout()">Add to basket</button>
      <button class="btn btnGhost full">Finance calculator</button>
    </aside>
  </section>

  <section id="presets" class="presets">
    <div class="presetsTop">
      <div><h2>Popular builds</h2><p class="muted">Load a finished layout and customise it.</p></div>
    </div>
    <div class="presetGrid">
      <div class="preset" onclick="loadBuild('entertainer')"><img src="{{ url_for('static', filename='img/preset-entertainer.jpg') }}"><div><span>The Entertainer</span><strong>£9,995</strong></div></div>
      <div class="preset" onclick="loadBuild('family')"><img src="{{ url_for('static', filename='img/preset-family.jpg') }}"><div><span>The Family Feast</span><strong>£12,450</strong></div></div>
      <div class="preset" onclick="loadBuild('chef')"><img src="{{ url_for('static', filename='img/preset-chef.jpg') }}"><div><span>The Chef's Dream</span><strong>£15,750</strong></div></div>
      <div class="preset" onclick="loadBuild('ultimate')"><img src="{{ url_for('static', filename='img/preset-ultimate.jpg') }}"><div><span>The Ultimate Space</span><strong>£21,995</strong></div></div>
    </div>
  </section>

  <footer class="footer">
    <div class="foot"><i>🛡</i><div><b>Built to last</b><span>Premium materials.</span></div></div>
    <div class="foot"><i>🛠</i><div><b>Modular design</b><span>Add or upgrade anytime.</span></div></div>
    <div class="foot"><i>🚚</i><div><b>UK manufactured</b><span>Precision engineered.</span></div></div>
    <div class="foot"><i>🇬🇧</i><div><b>Built in Britain</b><span>Manufactured by CE Turner.</span></div></div>
  </footer>
</div>

<div id="checkout" class="checkout">
  <div class="checkoutCard">
    <h1>Complete Your Invictus Design</h1>
    <div id="checkoutSummary"></div>
    <h3>Customer Details</h3>
    <div class="formGrid">
      <input placeholder="Name">
      <input placeholder="Email">
      <input placeholder="Phone">
      <input placeholder="Postcode">
    </div>
    <textarea style="margin-top:12px" placeholder="Delivery access, installation notes, finish preference"></textarea>
    <p>
      <button class="btn btnPrimary">Submit enquiry / pay deposit</button>
      <button class="btn btnGhost" onclick="closeCheckout()">Close</button>
    </p>
  </div>
</div>

<script src="{{ url_for('static', filename='app.js') }}"></script>
</body>
</html>
