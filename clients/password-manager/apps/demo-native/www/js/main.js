// ../../node_modules/@capacitor/core/dist/index.js
var createCapacitorPlatforms = (win) => {
  const defaultPlatformMap = /* @__PURE__ */ new Map();
  defaultPlatformMap.set("web", { name: "web" });
  const capPlatforms = win.CapacitorPlatforms || {
    currentPlatform: { name: "web" },
    platforms: defaultPlatformMap
  };
  const addPlatform2 = (name, platform) => {
    capPlatforms.platforms.set(name, platform);
  };
  const setPlatform2 = (name) => {
    if (capPlatforms.platforms.has(name)) {
      capPlatforms.currentPlatform = capPlatforms.platforms.get(name);
    }
  };
  capPlatforms.addPlatform = addPlatform2;
  capPlatforms.setPlatform = setPlatform2;
  return capPlatforms;
};
var initPlatforms = (win) => win.CapacitorPlatforms = createCapacitorPlatforms(win);
var CapacitorPlatforms = /* @__PURE__ */ initPlatforms(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : typeof global !== "undefined" ? global : {});
var addPlatform = CapacitorPlatforms.addPlatform;
var setPlatform = CapacitorPlatforms.setPlatform;
var ExceptionCode;
(function(ExceptionCode2) {
  ExceptionCode2["Unimplemented"] = "UNIMPLEMENTED";
  ExceptionCode2["Unavailable"] = "UNAVAILABLE";
})(ExceptionCode || (ExceptionCode = {}));
var CapacitorException = class extends Error {
  constructor(message, code, data) {
    super(message);
    this.message = message;
    this.code = code;
    this.data = data;
  }
};
var getPlatformId = (win) => {
  var _a, _b;
  if (win === null || win === void 0 ? void 0 : win.androidBridge) {
    return "android";
  } else if ((_b = (_a = win === null || win === void 0 ? void 0 : win.webkit) === null || _a === void 0 ? void 0 : _a.messageHandlers) === null || _b === void 0 ? void 0 : _b.bridge) {
    return "ios";
  } else {
    return "web";
  }
};
var createCapacitor = (win) => {
  var _a, _b, _c, _d, _e;
  const capCustomPlatform = win.CapacitorCustomPlatform || null;
  const cap = win.Capacitor || {};
  const Plugins2 = cap.Plugins = cap.Plugins || {};
  const capPlatforms = win.CapacitorPlatforms;
  const defaultGetPlatform = () => {
    return capCustomPlatform !== null ? capCustomPlatform.name : getPlatformId(win);
  };
  const getPlatform = ((_a = capPlatforms === null || capPlatforms === void 0 ? void 0 : capPlatforms.currentPlatform) === null || _a === void 0 ? void 0 : _a.getPlatform) || defaultGetPlatform;
  const defaultIsNativePlatform = () => getPlatform() !== "web";
  const isNativePlatform = ((_b = capPlatforms === null || capPlatforms === void 0 ? void 0 : capPlatforms.currentPlatform) === null || _b === void 0 ? void 0 : _b.isNativePlatform) || defaultIsNativePlatform;
  const defaultIsPluginAvailable = (pluginName) => {
    const plugin = registeredPlugins.get(pluginName);
    if (plugin === null || plugin === void 0 ? void 0 : plugin.platforms.has(getPlatform())) {
      return true;
    }
    if (getPluginHeader(pluginName)) {
      return true;
    }
    return false;
  };
  const isPluginAvailable = ((_c = capPlatforms === null || capPlatforms === void 0 ? void 0 : capPlatforms.currentPlatform) === null || _c === void 0 ? void 0 : _c.isPluginAvailable) || defaultIsPluginAvailable;
  const defaultGetPluginHeader = (pluginName) => {
    var _a2;
    return (_a2 = cap.PluginHeaders) === null || _a2 === void 0 ? void 0 : _a2.find((h) => h.name === pluginName);
  };
  const getPluginHeader = ((_d = capPlatforms === null || capPlatforms === void 0 ? void 0 : capPlatforms.currentPlatform) === null || _d === void 0 ? void 0 : _d.getPluginHeader) || defaultGetPluginHeader;
  const handleError = (err) => win.console.error(err);
  const pluginMethodNoop = (_target, prop, pluginName) => {
    return Promise.reject(`${pluginName} does not have an implementation of "${prop}".`);
  };
  const registeredPlugins = /* @__PURE__ */ new Map();
  const defaultRegisterPlugin = (pluginName, jsImplementations = {}) => {
    const registeredPlugin = registeredPlugins.get(pluginName);
    if (registeredPlugin) {
      console.warn(`Capacitor plugin "${pluginName}" already registered. Cannot register plugins twice.`);
      return registeredPlugin.proxy;
    }
    const platform = getPlatform();
    const pluginHeader = getPluginHeader(pluginName);
    let jsImplementation;
    const loadPluginImplementation = async () => {
      if (!jsImplementation && platform in jsImplementations) {
        jsImplementation = typeof jsImplementations[platform] === "function" ? jsImplementation = await jsImplementations[platform]() : jsImplementation = jsImplementations[platform];
      } else if (capCustomPlatform !== null && !jsImplementation && "web" in jsImplementations) {
        jsImplementation = typeof jsImplementations["web"] === "function" ? jsImplementation = await jsImplementations["web"]() : jsImplementation = jsImplementations["web"];
      }
      return jsImplementation;
    };
    const createPluginMethod = (impl, prop) => {
      var _a2, _b2;
      if (pluginHeader) {
        const methodHeader = pluginHeader === null || pluginHeader === void 0 ? void 0 : pluginHeader.methods.find((m) => prop === m.name);
        if (methodHeader) {
          if (methodHeader.rtype === "promise") {
            return (options) => cap.nativePromise(pluginName, prop.toString(), options);
          } else {
            return (options, callback) => cap.nativeCallback(pluginName, prop.toString(), options, callback);
          }
        } else if (impl) {
          return (_a2 = impl[prop]) === null || _a2 === void 0 ? void 0 : _a2.bind(impl);
        }
      } else if (impl) {
        return (_b2 = impl[prop]) === null || _b2 === void 0 ? void 0 : _b2.bind(impl);
      } else {
        throw new CapacitorException(`"${pluginName}" plugin is not implemented on ${platform}`, ExceptionCode.Unimplemented);
      }
    };
    const createPluginMethodWrapper = (prop) => {
      let remove;
      const wrapper = (...args) => {
        const p = loadPluginImplementation().then((impl) => {
          const fn = createPluginMethod(impl, prop);
          if (fn) {
            const p2 = fn(...args);
            remove = p2 === null || p2 === void 0 ? void 0 : p2.remove;
            return p2;
          } else {
            throw new CapacitorException(`"${pluginName}.${prop}()" is not implemented on ${platform}`, ExceptionCode.Unimplemented);
          }
        });
        if (prop === "addListener") {
          p.remove = async () => remove();
        }
        return p;
      };
      wrapper.toString = () => `${prop.toString()}() { [capacitor code] }`;
      Object.defineProperty(wrapper, "name", {
        value: prop,
        writable: false,
        configurable: false
      });
      return wrapper;
    };
    const addListener = createPluginMethodWrapper("addListener");
    const removeListener = createPluginMethodWrapper("removeListener");
    const addListenerNative = (eventName, callback) => {
      const call = addListener({ eventName }, callback);
      const remove = async () => {
        const callbackId = await call;
        removeListener({
          eventName,
          callbackId
        }, callback);
      };
      const p = new Promise((resolve) => call.then(() => resolve({ remove })));
      p.remove = async () => {
        console.warn(`Using addListener() without 'await' is deprecated.`);
        await remove();
      };
      return p;
    };
    const proxy = new Proxy({}, {
      get(_, prop) {
        switch (prop) {
          // https://github.com/facebook/react/issues/20030
          case "$$typeof":
            return void 0;
          case "toJSON":
            return () => ({});
          case "addListener":
            return pluginHeader ? addListenerNative : addListener;
          case "removeListener":
            return removeListener;
          default:
            return createPluginMethodWrapper(prop);
        }
      }
    });
    Plugins2[pluginName] = proxy;
    registeredPlugins.set(pluginName, {
      name: pluginName,
      proxy,
      platforms: /* @__PURE__ */ new Set([
        ...Object.keys(jsImplementations),
        ...pluginHeader ? [platform] : []
      ])
    });
    return proxy;
  };
  const registerPlugin2 = ((_e = capPlatforms === null || capPlatforms === void 0 ? void 0 : capPlatforms.currentPlatform) === null || _e === void 0 ? void 0 : _e.registerPlugin) || defaultRegisterPlugin;
  if (!cap.convertFileSrc) {
    cap.convertFileSrc = (filePath) => filePath;
  }
  cap.getPlatform = getPlatform;
  cap.handleError = handleError;
  cap.isNativePlatform = isNativePlatform;
  cap.isPluginAvailable = isPluginAvailable;
  cap.pluginMethodNoop = pluginMethodNoop;
  cap.registerPlugin = registerPlugin2;
  cap.Exception = CapacitorException;
  cap.DEBUG = !!cap.DEBUG;
  cap.isLoggingEnabled = !!cap.isLoggingEnabled;
  cap.platform = cap.getPlatform();
  cap.isNative = cap.isNativePlatform();
  return cap;
};
var initCapacitorGlobal = (win) => win.Capacitor = createCapacitor(win);
var Capacitor = /* @__PURE__ */ initCapacitorGlobal(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : typeof global !== "undefined" ? global : {});
var registerPlugin = Capacitor.registerPlugin;
var Plugins = Capacitor.Plugins;
var WebPlugin = class {
  constructor(config) {
    this.listeners = {};
    this.retainedEventArguments = {};
    this.windowListeners = {};
    if (config) {
      console.warn(`Capacitor WebPlugin "${config.name}" config object was deprecated in v3 and will be removed in v4.`);
      this.config = config;
    }
  }
  addListener(eventName, listenerFunc) {
    let firstListener = false;
    const listeners = this.listeners[eventName];
    if (!listeners) {
      this.listeners[eventName] = [];
      firstListener = true;
    }
    this.listeners[eventName].push(listenerFunc);
    const windowListener = this.windowListeners[eventName];
    if (windowListener && !windowListener.registered) {
      this.addWindowListener(windowListener);
    }
    if (firstListener) {
      this.sendRetainedArgumentsForEvent(eventName);
    }
    const remove = async () => this.removeListener(eventName, listenerFunc);
    const p = Promise.resolve({ remove });
    return p;
  }
  async removeAllListeners() {
    this.listeners = {};
    for (const listener in this.windowListeners) {
      this.removeWindowListener(this.windowListeners[listener]);
    }
    this.windowListeners = {};
  }
  notifyListeners(eventName, data, retainUntilConsumed) {
    const listeners = this.listeners[eventName];
    if (!listeners) {
      if (retainUntilConsumed) {
        let args = this.retainedEventArguments[eventName];
        if (!args) {
          args = [];
        }
        args.push(data);
        this.retainedEventArguments[eventName] = args;
      }
      return;
    }
    listeners.forEach((listener) => listener(data));
  }
  hasListeners(eventName) {
    return !!this.listeners[eventName].length;
  }
  registerWindowListener(windowEventName, pluginEventName) {
    this.windowListeners[pluginEventName] = {
      registered: false,
      windowEventName,
      pluginEventName,
      handler: (event) => {
        this.notifyListeners(pluginEventName, event);
      }
    };
  }
  unimplemented(msg = "not implemented") {
    return new Capacitor.Exception(msg, ExceptionCode.Unimplemented);
  }
  unavailable(msg = "not available") {
    return new Capacitor.Exception(msg, ExceptionCode.Unavailable);
  }
  async removeListener(eventName, listenerFunc) {
    const listeners = this.listeners[eventName];
    if (!listeners) {
      return;
    }
    const index = listeners.indexOf(listenerFunc);
    this.listeners[eventName].splice(index, 1);
    if (!this.listeners[eventName].length) {
      this.removeWindowListener(this.windowListeners[eventName]);
    }
  }
  addWindowListener(handle) {
    window.addEventListener(handle.windowEventName, handle.handler);
    handle.registered = true;
  }
  removeWindowListener(handle) {
    if (!handle) {
      return;
    }
    window.removeEventListener(handle.windowEventName, handle.handler);
    handle.registered = false;
  }
  sendRetainedArgumentsForEvent(eventName) {
    const args = this.retainedEventArguments[eventName];
    if (!args) {
      return;
    }
    delete this.retainedEventArguments[eventName];
    args.forEach((arg) => {
      this.notifyListeners(eventName, arg);
    });
  }
};
var encode = (str) => encodeURIComponent(str).replace(/%(2[346B]|5E|60|7C)/g, decodeURIComponent).replace(/[()]/g, escape);
var decode = (str) => str.replace(/(%[\dA-F]{2})+/gi, decodeURIComponent);
var CapacitorCookiesPluginWeb = class extends WebPlugin {
  async getCookies() {
    const cookies = document.cookie;
    const cookieMap = {};
    cookies.split(";").forEach((cookie) => {
      if (cookie.length <= 0)
        return;
      let [key, value] = cookie.replace(/=/, "CAP_COOKIE").split("CAP_COOKIE");
      key = decode(key).trim();
      value = decode(value).trim();
      cookieMap[key] = value;
    });
    return cookieMap;
  }
  async setCookie(options) {
    try {
      const encodedKey = encode(options.key);
      const encodedValue = encode(options.value);
      const expires = `; expires=${(options.expires || "").replace("expires=", "")}`;
      const path = (options.path || "/").replace("path=", "");
      const domain = options.url != null && options.url.length > 0 ? `domain=${options.url}` : "";
      document.cookie = `${encodedKey}=${encodedValue || ""}${expires}; path=${path}; ${domain};`;
    } catch (error) {
      return Promise.reject(error);
    }
  }
  async deleteCookie(options) {
    try {
      document.cookie = `${options.key}=; Max-Age=0`;
    } catch (error) {
      return Promise.reject(error);
    }
  }
  async clearCookies() {
    try {
      const cookies = document.cookie.split(";") || [];
      for (const cookie of cookies) {
        document.cookie = cookie.replace(/^ +/, "").replace(/=.*/, `=;expires=${(/* @__PURE__ */ new Date()).toUTCString()};path=/`);
      }
    } catch (error) {
      return Promise.reject(error);
    }
  }
  async clearAllCookies() {
    try {
      await this.clearCookies();
    } catch (error) {
      return Promise.reject(error);
    }
  }
};
var CapacitorCookies = registerPlugin("CapacitorCookies", {
  web: () => new CapacitorCookiesPluginWeb()
});
var readBlobAsBase64 = async (blob) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => {
    const base64String = reader.result;
    resolve(base64String.indexOf(",") >= 0 ? base64String.split(",")[1] : base64String);
  };
  reader.onerror = (error) => reject(error);
  reader.readAsDataURL(blob);
});
var normalizeHttpHeaders = (headers = {}) => {
  const originalKeys = Object.keys(headers);
  const loweredKeys = Object.keys(headers).map((k) => k.toLocaleLowerCase());
  const normalized = loweredKeys.reduce((acc, key, index) => {
    acc[key] = headers[originalKeys[index]];
    return acc;
  }, {});
  return normalized;
};
var buildUrlParams = (params, shouldEncode = true) => {
  if (!params)
    return null;
  const output = Object.entries(params).reduce((accumulator, entry) => {
    const [key, value] = entry;
    let encodedValue;
    let item;
    if (Array.isArray(value)) {
      item = "";
      value.forEach((str) => {
        encodedValue = shouldEncode ? encodeURIComponent(str) : str;
        item += `${key}=${encodedValue}&`;
      });
      item.slice(0, -1);
    } else {
      encodedValue = shouldEncode ? encodeURIComponent(value) : value;
      item = `${key}=${encodedValue}`;
    }
    return `${accumulator}&${item}`;
  }, "");
  return output.substr(1);
};
var buildRequestInit = (options, extra = {}) => {
  const output = Object.assign({ method: options.method || "GET", headers: options.headers }, extra);
  const headers = normalizeHttpHeaders(options.headers);
  const type = headers["content-type"] || "";
  if (typeof options.data === "string") {
    output.body = options.data;
  } else if (type.includes("application/x-www-form-urlencoded")) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(options.data || {})) {
      params.set(key, value);
    }
    output.body = params.toString();
  } else if (type.includes("multipart/form-data") || options.data instanceof FormData) {
    const form = new FormData();
    if (options.data instanceof FormData) {
      options.data.forEach((value, key) => {
        form.append(key, value);
      });
    } else {
      for (const key of Object.keys(options.data)) {
        form.append(key, options.data[key]);
      }
    }
    output.body = form;
    const headers2 = new Headers(output.headers);
    headers2.delete("content-type");
    output.headers = headers2;
  } else if (type.includes("application/json") || typeof options.data === "object") {
    output.body = JSON.stringify(options.data);
  }
  return output;
};
var CapacitorHttpPluginWeb = class extends WebPlugin {
  /**
   * Perform an Http request given a set of options
   * @param options Options to build the HTTP request
   */
  async request(options) {
    const requestInit = buildRequestInit(options, options.webFetchExtra);
    const urlParams = buildUrlParams(options.params, options.shouldEncodeUrlParams);
    const url = urlParams ? `${options.url}?${urlParams}` : options.url;
    const response = await fetch(url, requestInit);
    const contentType = response.headers.get("content-type") || "";
    let { responseType = "text" } = response.ok ? options : {};
    if (contentType.includes("application/json")) {
      responseType = "json";
    }
    let data;
    let blob;
    switch (responseType) {
      case "arraybuffer":
      case "blob":
        blob = await response.blob();
        data = await readBlobAsBase64(blob);
        break;
      case "json":
        data = await response.json();
        break;
      case "document":
      case "text":
      default:
        data = await response.text();
    }
    const headers = {};
    response.headers.forEach((value, key) => {
      headers[key] = value;
    });
    return {
      data,
      headers,
      status: response.status,
      url: response.url
    };
  }
  /**
   * Perform an Http GET request given a set of options
   * @param options Options to build the HTTP request
   */
  async get(options) {
    return this.request(Object.assign(Object.assign({}, options), { method: "GET" }));
  }
  /**
   * Perform an Http POST request given a set of options
   * @param options Options to build the HTTP request
   */
  async post(options) {
    return this.request(Object.assign(Object.assign({}, options), { method: "POST" }));
  }
  /**
   * Perform an Http PUT request given a set of options
   * @param options Options to build the HTTP request
   */
  async put(options) {
    return this.request(Object.assign(Object.assign({}, options), { method: "PUT" }));
  }
  /**
   * Perform an Http PATCH request given a set of options
   * @param options Options to build the HTTP request
   */
  async patch(options) {
    return this.request(Object.assign(Object.assign({}, options), { method: "PATCH" }));
  }
  /**
   * Perform an Http DELETE request given a set of options
   * @param options Options to build the HTTP request
   */
  async delete(options) {
    return this.request(Object.assign(Object.assign({}, options), { method: "DELETE" }));
  }
};
var CapacitorHttp = registerPlugin("CapacitorHttp", {
  web: () => new CapacitorHttpPluginWeb()
});

// ../../node_modules/@scure/bip39/esm/wordlists/english.js
var wordlist = `abandon
ability
able
about
above
absent
absorb
abstract
absurd
abuse
access
accident
account
accuse
achieve
acid
acoustic
acquire
across
act
action
actor
actress
actual
adapt
add
addict
address
adjust
admit
adult
advance
advice
aerobic
affair
afford
afraid
again
age
agent
agree
ahead
aim
air
airport
aisle
alarm
album
alcohol
alert
alien
all
alley
allow
almost
alone
alpha
already
also
alter
always
amateur
amazing
among
amount
amused
analyst
anchor
ancient
anger
angle
angry
animal
ankle
announce
annual
another
answer
antenna
antique
anxiety
any
apart
apology
appear
apple
approve
april
arch
arctic
area
arena
argue
arm
armed
armor
army
around
arrange
arrest
arrive
arrow
art
artefact
artist
artwork
ask
aspect
assault
asset
assist
assume
asthma
athlete
atom
attack
attend
attitude
attract
auction
audit
august
aunt
author
auto
autumn
average
avocado
avoid
awake
aware
away
awesome
awful
awkward
axis
baby
bachelor
bacon
badge
bag
balance
balcony
ball
bamboo
banana
banner
bar
barely
bargain
barrel
base
basic
basket
battle
beach
bean
beauty
because
become
beef
before
begin
behave
behind
believe
below
belt
bench
benefit
best
betray
better
between
beyond
bicycle
bid
bike
bind
biology
bird
birth
bitter
black
blade
blame
blanket
blast
bleak
bless
blind
blood
blossom
blouse
blue
blur
blush
board
boat
body
boil
bomb
bone
bonus
book
boost
border
boring
borrow
boss
bottom
bounce
box
boy
bracket
brain
brand
brass
brave
bread
breeze
brick
bridge
brief
bright
bring
brisk
broccoli
broken
bronze
broom
brother
brown
brush
bubble
buddy
budget
buffalo
build
bulb
bulk
bullet
bundle
bunker
burden
burger
burst
bus
business
busy
butter
buyer
buzz
cabbage
cabin
cable
cactus
cage
cake
call
calm
camera
camp
can
canal
cancel
candy
cannon
canoe
canvas
canyon
capable
capital
captain
car
carbon
card
cargo
carpet
carry
cart
case
cash
casino
castle
casual
cat
catalog
catch
category
cattle
caught
cause
caution
cave
ceiling
celery
cement
census
century
cereal
certain
chair
chalk
champion
change
chaos
chapter
charge
chase
chat
cheap
check
cheese
chef
cherry
chest
chicken
chief
child
chimney
choice
choose
chronic
chuckle
chunk
churn
cigar
cinnamon
circle
citizen
city
civil
claim
clap
clarify
claw
clay
clean
clerk
clever
click
client
cliff
climb
clinic
clip
clock
clog
close
cloth
cloud
clown
club
clump
cluster
clutch
coach
coast
coconut
code
coffee
coil
coin
collect
color
column
combine
come
comfort
comic
common
company
concert
conduct
confirm
congress
connect
consider
control
convince
cook
cool
copper
copy
coral
core
corn
correct
cost
cotton
couch
country
couple
course
cousin
cover
coyote
crack
cradle
craft
cram
crane
crash
crater
crawl
crazy
cream
credit
creek
crew
cricket
crime
crisp
critic
crop
cross
crouch
crowd
crucial
cruel
cruise
crumble
crunch
crush
cry
crystal
cube
culture
cup
cupboard
curious
current
curtain
curve
cushion
custom
cute
cycle
dad
damage
damp
dance
danger
daring
dash
daughter
dawn
day
deal
debate
debris
decade
december
decide
decline
decorate
decrease
deer
defense
define
defy
degree
delay
deliver
demand
demise
denial
dentist
deny
depart
depend
deposit
depth
deputy
derive
describe
desert
design
desk
despair
destroy
detail
detect
develop
device
devote
diagram
dial
diamond
diary
dice
diesel
diet
differ
digital
dignity
dilemma
dinner
dinosaur
direct
dirt
disagree
discover
disease
dish
dismiss
disorder
display
distance
divert
divide
divorce
dizzy
doctor
document
dog
doll
dolphin
domain
donate
donkey
donor
door
dose
double
dove
draft
dragon
drama
drastic
draw
dream
dress
drift
drill
drink
drip
drive
drop
drum
dry
duck
dumb
dune
during
dust
dutch
duty
dwarf
dynamic
eager
eagle
early
earn
earth
easily
east
easy
echo
ecology
economy
edge
edit
educate
effort
egg
eight
either
elbow
elder
electric
elegant
element
elephant
elevator
elite
else
embark
embody
embrace
emerge
emotion
employ
empower
empty
enable
enact
end
endless
endorse
enemy
energy
enforce
engage
engine
enhance
enjoy
enlist
enough
enrich
enroll
ensure
enter
entire
entry
envelope
episode
equal
equip
era
erase
erode
erosion
error
erupt
escape
essay
essence
estate
eternal
ethics
evidence
evil
evoke
evolve
exact
example
excess
exchange
excite
exclude
excuse
execute
exercise
exhaust
exhibit
exile
exist
exit
exotic
expand
expect
expire
explain
expose
express
extend
extra
eye
eyebrow
fabric
face
faculty
fade
faint
faith
fall
false
fame
family
famous
fan
fancy
fantasy
farm
fashion
fat
fatal
father
fatigue
fault
favorite
feature
february
federal
fee
feed
feel
female
fence
festival
fetch
fever
few
fiber
fiction
field
figure
file
film
filter
final
find
fine
finger
finish
fire
firm
first
fiscal
fish
fit
fitness
fix
flag
flame
flash
flat
flavor
flee
flight
flip
float
flock
floor
flower
fluid
flush
fly
foam
focus
fog
foil
fold
follow
food
foot
force
forest
forget
fork
fortune
forum
forward
fossil
foster
found
fox
fragile
frame
frequent
fresh
friend
fringe
frog
front
frost
frown
frozen
fruit
fuel
fun
funny
furnace
fury
future
gadget
gain
galaxy
gallery
game
gap
garage
garbage
garden
garlic
garment
gas
gasp
gate
gather
gauge
gaze
general
genius
genre
gentle
genuine
gesture
ghost
giant
gift
giggle
ginger
giraffe
girl
give
glad
glance
glare
glass
glide
glimpse
globe
gloom
glory
glove
glow
glue
goat
goddess
gold
good
goose
gorilla
gospel
gossip
govern
gown
grab
grace
grain
grant
grape
grass
gravity
great
green
grid
grief
grit
grocery
group
grow
grunt
guard
guess
guide
guilt
guitar
gun
gym
habit
hair
half
hammer
hamster
hand
happy
harbor
hard
harsh
harvest
hat
have
hawk
hazard
head
health
heart
heavy
hedgehog
height
hello
helmet
help
hen
hero
hidden
high
hill
hint
hip
hire
history
hobby
hockey
hold
hole
holiday
hollow
home
honey
hood
hope
horn
horror
horse
hospital
host
hotel
hour
hover
hub
huge
human
humble
humor
hundred
hungry
hunt
hurdle
hurry
hurt
husband
hybrid
ice
icon
idea
identify
idle
ignore
ill
illegal
illness
image
imitate
immense
immune
impact
impose
improve
impulse
inch
include
income
increase
index
indicate
indoor
industry
infant
inflict
inform
inhale
inherit
initial
inject
injury
inmate
inner
innocent
input
inquiry
insane
insect
inside
inspire
install
intact
interest
into
invest
invite
involve
iron
island
isolate
issue
item
ivory
jacket
jaguar
jar
jazz
jealous
jeans
jelly
jewel
job
join
joke
journey
joy
judge
juice
jump
jungle
junior
junk
just
kangaroo
keen
keep
ketchup
key
kick
kid
kidney
kind
kingdom
kiss
kit
kitchen
kite
kitten
kiwi
knee
knife
knock
know
lab
label
labor
ladder
lady
lake
lamp
language
laptop
large
later
latin
laugh
laundry
lava
law
lawn
lawsuit
layer
lazy
leader
leaf
learn
leave
lecture
left
leg
legal
legend
leisure
lemon
lend
length
lens
leopard
lesson
letter
level
liar
liberty
library
license
life
lift
light
like
limb
limit
link
lion
liquid
list
little
live
lizard
load
loan
lobster
local
lock
logic
lonely
long
loop
lottery
loud
lounge
love
loyal
lucky
luggage
lumber
lunar
lunch
luxury
lyrics
machine
mad
magic
magnet
maid
mail
main
major
make
mammal
man
manage
mandate
mango
mansion
manual
maple
marble
march
margin
marine
market
marriage
mask
mass
master
match
material
math
matrix
matter
maximum
maze
meadow
mean
measure
meat
mechanic
medal
media
melody
melt
member
memory
mention
menu
mercy
merge
merit
merry
mesh
message
metal
method
middle
midnight
milk
million
mimic
mind
minimum
minor
minute
miracle
mirror
misery
miss
mistake
mix
mixed
mixture
mobile
model
modify
mom
moment
monitor
monkey
monster
month
moon
moral
more
morning
mosquito
mother
motion
motor
mountain
mouse
move
movie
much
muffin
mule
multiply
muscle
museum
mushroom
music
must
mutual
myself
mystery
myth
naive
name
napkin
narrow
nasty
nation
nature
near
neck
need
negative
neglect
neither
nephew
nerve
nest
net
network
neutral
never
news
next
nice
night
noble
noise
nominee
noodle
normal
north
nose
notable
note
nothing
notice
novel
now
nuclear
number
nurse
nut
oak
obey
object
oblige
obscure
observe
obtain
obvious
occur
ocean
october
odor
off
offer
office
often
oil
okay
old
olive
olympic
omit
once
one
onion
online
only
open
opera
opinion
oppose
option
orange
orbit
orchard
order
ordinary
organ
orient
original
orphan
ostrich
other
outdoor
outer
output
outside
oval
oven
over
own
owner
oxygen
oyster
ozone
pact
paddle
page
pair
palace
palm
panda
panel
panic
panther
paper
parade
parent
park
parrot
party
pass
patch
path
patient
patrol
pattern
pause
pave
payment
peace
peanut
pear
peasant
pelican
pen
penalty
pencil
people
pepper
perfect
permit
person
pet
phone
photo
phrase
physical
piano
picnic
picture
piece
pig
pigeon
pill
pilot
pink
pioneer
pipe
pistol
pitch
pizza
place
planet
plastic
plate
play
please
pledge
pluck
plug
plunge
poem
poet
point
polar
pole
police
pond
pony
pool
popular
portion
position
possible
post
potato
pottery
poverty
powder
power
practice
praise
predict
prefer
prepare
present
pretty
prevent
price
pride
primary
print
priority
prison
private
prize
problem
process
produce
profit
program
project
promote
proof
property
prosper
protect
proud
provide
public
pudding
pull
pulp
pulse
pumpkin
punch
pupil
puppy
purchase
purity
purpose
purse
push
put
puzzle
pyramid
quality
quantum
quarter
question
quick
quit
quiz
quote
rabbit
raccoon
race
rack
radar
radio
rail
rain
raise
rally
ramp
ranch
random
range
rapid
rare
rate
rather
raven
raw
razor
ready
real
reason
rebel
rebuild
recall
receive
recipe
record
recycle
reduce
reflect
reform
refuse
region
regret
regular
reject
relax
release
relief
rely
remain
remember
remind
remove
render
renew
rent
reopen
repair
repeat
replace
report
require
rescue
resemble
resist
resource
response
result
retire
retreat
return
reunion
reveal
review
reward
rhythm
rib
ribbon
rice
rich
ride
ridge
rifle
right
rigid
ring
riot
ripple
risk
ritual
rival
river
road
roast
robot
robust
rocket
romance
roof
rookie
room
rose
rotate
rough
round
route
royal
rubber
rude
rug
rule
run
runway
rural
sad
saddle
sadness
safe
sail
salad
salmon
salon
salt
salute
same
sample
sand
satisfy
satoshi
sauce
sausage
save
say
scale
scan
scare
scatter
scene
scheme
school
science
scissors
scorpion
scout
scrap
screen
script
scrub
sea
search
season
seat
second
secret
section
security
seed
seek
segment
select
sell
seminar
senior
sense
sentence
series
service
session
settle
setup
seven
shadow
shaft
shallow
share
shed
shell
sheriff
shield
shift
shine
ship
shiver
shock
shoe
shoot
shop
short
shoulder
shove
shrimp
shrug
shuffle
shy
sibling
sick
side
siege
sight
sign
silent
silk
silly
silver
similar
simple
since
sing
siren
sister
situate
six
size
skate
sketch
ski
skill
skin
skirt
skull
slab
slam
sleep
slender
slice
slide
slight
slim
slogan
slot
slow
slush
small
smart
smile
smoke
smooth
snack
snake
snap
sniff
snow
soap
soccer
social
sock
soda
soft
solar
soldier
solid
solution
solve
someone
song
soon
sorry
sort
soul
sound
soup
source
south
space
spare
spatial
spawn
speak
special
speed
spell
spend
sphere
spice
spider
spike
spin
spirit
split
spoil
sponsor
spoon
sport
spot
spray
spread
spring
spy
square
squeeze
squirrel
stable
stadium
staff
stage
stairs
stamp
stand
start
state
stay
steak
steel
stem
step
stereo
stick
still
sting
stock
stomach
stone
stool
story
stove
strategy
street
strike
strong
struggle
student
stuff
stumble
style
subject
submit
subway
success
such
sudden
suffer
sugar
suggest
suit
summer
sun
sunny
sunset
super
supply
supreme
sure
surface
surge
surprise
surround
survey
suspect
sustain
swallow
swamp
swap
swarm
swear
sweet
swift
swim
swing
switch
sword
symbol
symptom
syrup
system
table
tackle
tag
tail
talent
talk
tank
tape
target
task
taste
tattoo
taxi
teach
team
tell
ten
tenant
tennis
tent
term
test
text
thank
that
theme
then
theory
there
they
thing
this
thought
three
thrive
throw
thumb
thunder
ticket
tide
tiger
tilt
timber
time
tiny
tip
tired
tissue
title
toast
tobacco
today
toddler
toe
together
toilet
token
tomato
tomorrow
tone
tongue
tonight
tool
tooth
top
topic
topple
torch
tornado
tortoise
toss
total
tourist
toward
tower
town
toy
track
trade
traffic
tragic
train
transfer
trap
trash
travel
tray
treat
tree
trend
trial
tribe
trick
trigger
trim
trip
trophy
trouble
truck
true
truly
trumpet
trust
truth
try
tube
tuition
tumble
tuna
tunnel
turkey
turn
turtle
twelve
twenty
twice
twin
twist
two
type
typical
ugly
umbrella
unable
unaware
uncle
uncover
under
undo
unfair
unfold
unhappy
uniform
unique
unit
universe
unknown
unlock
until
unusual
unveil
update
upgrade
uphold
upon
upper
upset
urban
urge
usage
use
used
useful
useless
usual
utility
vacant
vacuum
vague
valid
valley
valve
van
vanish
vapor
various
vast
vault
vehicle
velvet
vendor
venture
venue
verb
verify
version
very
vessel
veteran
viable
vibrant
vicious
victory
video
view
village
vintage
violin
virtual
virus
visa
visit
visual
vital
vivid
vocal
voice
void
volcano
volume
vote
voyage
wage
wagon
wait
walk
wall
walnut
want
warfare
warm
warrior
wash
wasp
waste
water
wave
way
wealth
weapon
wear
weasel
weather
web
wedding
weekend
weird
welcome
west
wet
whale
what
wheat
wheel
when
where
whip
whisper
wide
width
wife
wild
will
win
window
wine
wing
wink
winner
winter
wire
wisdom
wise
wish
witness
wolf
woman
wonder
wood
wool
word
work
world
worry
worth
wrap
wreck
wrestle
wrist
write
wrong
yard
year
yellow
you
young
youth
zebra
zero
zone
zoo`.split("\n");

// ../../packages/core/dist/derive.js
var CURVE_ORDER = BigInt("0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141");

// ../../node_modules/bcryptjs/index.js
var nextTick = typeof setImmediate === "function" ? setImmediate : typeof scheduler === "object" && typeof scheduler.postTask === "function" ? scheduler.postTask.bind(scheduler) : setTimeout;
var BASE64_CODE = "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789".split("");

// ../../packages/core/dist/box.js
var DOMAIN = new TextEncoder().encode("yada-pw-box-v1");

// ../../packages/core/dist/vault.js
function normalizeSiteId(siteId2) {
  const raw = siteId2.trim();
  if (!raw)
    return "";
  try {
    const withScheme = raw.includes("://") ? raw : `https://${raw}`;
    const u = new URL(withScheme);
    if (u.protocol !== "http:" && u.protocol !== "https:") {
      throw new Error("site origin must be http(s)");
    }
    return u.origin.toLowerCase();
  } catch {
    return raw.toLowerCase();
  }
}

// ../../packages/core/dist/deeplink.js
var DEMO_APP_SITE_ID = "yadademo://app";

// ../../packages/core/dist/auth-session.js
function base(url) {
  return (url || "").replace(/\/+$/, "");
}
async function jsonFetch(url, init) {
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.body ? { "Content-Type": "application/json" } : {},
      ...init?.headers || {}
    }
  });
  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text };
  }
  return { ok: res.ok, status: res.status, body };
}
async function createAuthSession(nodeUrl, req) {
  const { body } = await jsonFetch(base(nodeUrl) + "/password-rotation/auth-session", {
    method: "POST",
    body: JSON.stringify({
      username: req.username,
      site: req.site,
      action: req.action,
      expectedHash: req.expectedHash,
      nonce: req.nonce
    })
  });
  return body;
}
async function pollAuthSession(nodeUrl, sessionId) {
  const { body } = await jsonFetch(base(nodeUrl) + "/password-rotation/auth-session/" + encodeURIComponent(sessionId));
  return body;
}

// ../../packages/core/dist/network-topology.js
var TOPOLOGY_CACHE_TTL_MS = 6 * 60 * 60 * 1e3;
var TOPOLOGY_STALE_MAX_MS = 7 * 24 * 60 * 60 * 1e3;

// ../../packages/shared-ui/dist/theme/presets.js
var baseTypography = {
  fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  baseSizePx: 14,
  fontWeightNormal: 400,
  fontWeightBold: 600
};
var baseShape = {
  radiusSm: 6,
  radiusMd: 10,
  radiusLg: 16,
  density: "comfortable"
};
var DEFAULT_THEME = {
  id: "default",
  name: "Yada Light",
  mode: "light",
  brand: {
    name: "Yada Password"
  },
  colors: {
    background: "#f4f6f8",
    surface: "#ffffff",
    surfaceElevated: "#ffffff",
    text: "#0f172a",
    textMuted: "#64748b",
    primary: "#0d9488",
    primaryText: "#ffffff",
    danger: "#dc2626",
    dangerText: "#ffffff",
    success: "#16a34a",
    border: "#e2e8f0",
    focus: "#14b8a6",
    inputBackground: "#f8fafc",
    overlay: "rgba(15, 23, 42, 0.45)"
  },
  typography: { ...baseTypography },
  shape: { ...baseShape }
};
var DARK_THEME = {
  id: "dark",
  name: "Yada Dark",
  mode: "dark",
  brand: {
    name: "Yada Password"
  },
  colors: {
    background: "#0b1220",
    surface: "#111827",
    surfaceElevated: "#1f2937",
    text: "#f1f5f9",
    textMuted: "#94a3b8",
    primary: "#2dd4bf",
    primaryText: "#042f2e",
    danger: "#f87171",
    dangerText: "#450a0a",
    success: "#4ade80",
    border: "#334155",
    focus: "#5eead4",
    inputBackground: "#0f172a",
    overlay: "rgba(0, 0, 0, 0.55)"
  },
  typography: { ...baseTypography },
  shape: { ...baseShape }
};
var HIGH_CONTRAST_THEME = {
  id: "high-contrast",
  name: "High Contrast",
  mode: "dark",
  brand: {
    name: "Yada Password"
  },
  colors: {
    background: "#000000",
    surface: "#000000",
    surfaceElevated: "#0a0a0a",
    text: "#ffffff",
    textMuted: "#e5e5e5",
    primary: "#ffff00",
    primaryText: "#000000",
    danger: "#ff6b6b",
    dangerText: "#000000",
    success: "#00ff88",
    border: "#ffffff",
    focus: "#00ffff",
    inputBackground: "#000000",
    overlay: "rgba(0, 0, 0, 0.8)"
  },
  typography: {
    ...baseTypography,
    fontWeightBold: 700
  },
  shape: {
    ...baseShape,
    radiusSm: 2,
    radiusMd: 4,
    radiusLg: 6
  }
};
var PRESETS = {
  default: DEFAULT_THEME,
  dark: DARK_THEME,
  "high-contrast": HIGH_CONTRAST_THEME
};

// ../../packages/shared-ui/dist/theme/resolve.js
function prefersDark() {
  if (typeof window === "undefined" || !window.matchMedia)
    return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}
function deepMergeTheme(base2, overlay) {
  if (!overlay)
    return base2;
  return {
    id: overlay.id ?? base2.id,
    name: overlay.name ?? base2.name,
    mode: overlay.mode ?? base2.mode,
    brand: { ...base2.brand, ...overlay.brand },
    colors: { ...base2.colors, ...overlay.colors },
    typography: { ...base2.typography, ...overlay.typography },
    shape: { ...base2.shape, ...overlay.shape }
  };
}
function resolveMode(mode, systemPrefersDark) {
  if (mode === "light" || mode === "dark")
    return mode;
  const dark = systemPrefersDark ?? prefersDark();
  return dark ? "dark" : "light";
}
function resolveTheme(input = {}) {
  let base2 = DEFAULT_THEME;
  if (typeof input.preset === "string") {
    base2 = PRESETS[input.preset] ?? DEFAULT_THEME;
  } else if (input.preset) {
    base2 = input.preset;
  }
  let merged = deepMergeTheme(base2, input.remote);
  merged = deepMergeTheme(merged, input.user);
  const resolvedMode = resolveMode(merged.mode, input.systemPrefersDark);
  if (merged.mode === "system") {
    const modeBase = resolvedMode === "dark" ? DARK_THEME : DEFAULT_THEME;
    const colorOverrides = {
      ...input.remote?.colors,
      ...input.user?.colors
    };
    merged = {
      ...merged,
      colors: { ...modeBase.colors, ...colorOverrides }
    };
  }
  return {
    ...merged,
    resolvedMode
  };
}

// ../../packages/shared-ui/dist/theme/apply.js
var VAR_MAP = [
  ["--pm-bg", (t) => t.colors.background],
  ["--pm-surface", (t) => t.colors.surface],
  ["--pm-surface-elevated", (t) => t.colors.surfaceElevated],
  ["--pm-text", (t) => t.colors.text],
  ["--pm-text-muted", (t) => t.colors.textMuted],
  ["--pm-primary", (t) => t.colors.primary],
  ["--pm-primary-text", (t) => t.colors.primaryText],
  ["--pm-danger", (t) => t.colors.danger],
  ["--pm-danger-text", (t) => t.colors.dangerText],
  ["--pm-success", (t) => t.colors.success],
  ["--pm-border", (t) => t.colors.border],
  ["--pm-focus", (t) => t.colors.focus],
  ["--pm-input-bg", (t) => t.colors.inputBackground],
  ["--pm-overlay", (t) => t.colors.overlay],
  ["--pm-font", (t) => t.typography.fontFamily],
  ["--pm-font-size", (t) => `${t.typography.baseSizePx}px`],
  ["--pm-font-weight", (t) => t.typography.fontWeightNormal],
  ["--pm-font-weight-bold", (t) => t.typography.fontWeightBold],
  ["--pm-radius-sm", (t) => `${t.shape.radiusSm}px`],
  ["--pm-radius-md", (t) => `${t.shape.radiusMd}px`],
  ["--pm-radius-lg", (t) => `${t.shape.radiusLg}px`],
  [
    "--pm-space-unit",
    (t) => t.shape.density === "compact" ? "0.75rem" : "1rem"
  ]
];
function applyTheme(theme, root = typeof document !== "undefined" ? document.documentElement : null) {
  if (!root)
    return;
  for (const [cssVar, getter] of VAR_MAP) {
    root.style.setProperty(cssVar, String(getter(theme)));
  }
  root.dataset.theme = theme.id;
  root.dataset.mode = "resolvedMode" in theme && theme.resolvedMode ? theme.resolvedMode : theme.mode === "system" ? "light" : theme.mode;
  root.dataset.density = theme.shape.density;
  if (theme.brand?.name) {
    root.dataset.brand = theme.brand.name;
  }
}

// src/main.ts
var USER_KEY = "yadaDemoUsername";
var NODE_KEY = "yadaDemoNodeUrl";
var AUTH_KEY = "yadaDemoAuth";
function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`#${id}`);
  return el;
}
function alertMsg(msg, kind = "") {
  const el = $("alert");
  if (!msg) {
    el.hidden = true;
    el.textContent = "";
    el.className = "pm-alert";
    return;
  }
  el.hidden = false;
  el.textContent = msg;
  el.className = `pm-alert${kind ? ` pm-alert--${kind}` : ""}`;
}
function siteId() {
  return normalizeSiteId(DEMO_APP_SITE_ID);
}
function resolveNodeUrl(url) {
  let u = (url || "").trim().replace(/\/+$/, "");
  if (Capacitor.getPlatform() === "android") {
    u = u.replace(/127\.0\.0\.1/g, "10.0.2.2").replace(/localhost/gi, "10.0.2.2");
  }
  return u;
}
function pushLog(ok, note, counter) {
  const box = $("log");
  if (box.textContent === "No events yet") box.textContent = "";
  const row = document.createElement("div");
  row.className = "log-entry " + (ok ? "log-ok" : "log-bad");
  row.textContent = `${(/* @__PURE__ */ new Date()).toLocaleTimeString()} \xB7 ${ok ? "OK" : "FAIL"} \xB7 c=${counter ?? "\u2014"} \xB7 ${note}`;
  box.insertBefore(row, box.firstChild);
}
function loadAuth() {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
function saveAuth(auth) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
}
async function fetchTipPasswordHashes(nodeUrl) {
  const origin = siteId();
  const res = await fetch(
    nodeUrl + "/password-rotation/offchain/tip?branch_peer=" + encodeURIComponent(origin),
    { headers: { Accept: "application/json" } }
  );
  const data = await res.json();
  if (!res.ok || !data.status || !data.tip) return null;
  const pw = data.tip.password || {};
  return {
    pre: String(pw.prerotated_password_hash || ""),
    twice: String(pw.twice_prerotated_password_hash || ""),
    counter: Number(data.tip.counter ?? 0)
  };
}
var pollAbort = null;
function setBusy(busy) {
  for (const id of ["registerBtn", "signinBtn", "statusBtn"]) {
    $(id).disabled = busy;
  }
  const cancel = $("cancelBtn");
  if (cancel) cancel.disabled = !busy;
}
function applySession(action, view) {
  if (view.session_status === "denied" || view.session_status === "expired" || !view.ok) {
    pushLog(false, view.message || view.session_status || "failed", view.counter);
    alertMsg(view.message || view.session_status || "Failed", "error");
    return;
  }
  if (action === "signin" && !view.authenticated) {
    pushLog(false, "node did not verify the sealed password", view.counter);
    alertMsg("Auth failed: node did not verify the sealed password.", "error");
    return;
  }
  if (view.nextPasswordHash) saveAuth({ nextPasswordHash: view.nextPasswordHash });
  pushLog(true, view.message || action, view.counter);
  alertMsg(
    action === "signin" ? "Signed in. Node verified the sealed password against the tip." : view.message || "Approved",
    "success"
  );
}
async function startBridge(action) {
  if (pollAbort) pollAbort.abort();
  const username = ($("username").value || "").trim();
  const nodeUrl = resolveNodeUrl($("nodeUrl").value);
  localStorage.setItem(NODE_KEY, nodeUrl);
  localStorage.setItem(USER_KEY, username);
  if (!nodeUrl) {
    alertMsg("Set the node URL first.", "error");
    return;
  }
  if (!username) {
    alertMsg("Enter your Yada username.", "error");
    return;
  }
  let expectedHash;
  if (action === "signin") {
    try {
      const tip = await fetchTipPasswordHashes(nodeUrl);
      expectedHash = tip?.pre || loadAuth()?.nextPasswordHash;
    } catch {
      expectedHash = loadAuth()?.nextPasswordHash;
    }
  }
  pollAbort = new AbortController();
  const signal = pollAbort.signal;
  setBusy(true);
  alertMsg("Creating session\u2026", "");
  try {
    const created = await createAuthSession(nodeUrl, {
      username,
      site: siteId(),
      action,
      expectedHash
    });
    if (!created.status || !created.session_id) {
      throw new Error(created.message || "failed to create auth session");
    }
    alertMsg(
      created.delivered ? "Delivered. Approve in Yada Password." : "Open Yada Password so it can connect, then Approve.",
      ""
    );
    const started = Date.now();
    while (!signal.aborted) {
      if (Date.now() - started > 18e4) throw new Error("timed out waiting for approval");
      await new Promise((r) => setTimeout(r, 1500));
      if (signal.aborted) throw new Error("cancelled");
      const view = await pollAuthSession(nodeUrl, created.session_id);
      const st = view.session_status;
      if (st === "pending" || st === "delivered" || st === "proxied") continue;
      applySession(action, view);
      void refreshTip();
      return;
    }
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    if (message !== "cancelled") alertMsg(message, "error");
    else alertMsg("Cancelled", "error");
  } finally {
    setBusy(false);
    pollAbort = null;
  }
}
async function refreshTip() {
  const origin = siteId();
  $("siteId").textContent = origin;
  $("statusPill").textContent = "checking\u2026";
  $("statusPill").className = "pill";
  const nodeUrl = resolveNodeUrl($("nodeUrl").value);
  localStorage.setItem(NODE_KEY, nodeUrl);
  if (!nodeUrl) {
    $("statusPill").textContent = "set node URL";
    $("statusPill").className = "pill warn";
    return;
  }
  try {
    const tip = await fetchTipPasswordHashes(nodeUrl);
    if (!tip) {
      $("statusPill").textContent = "not registered";
      $("statusPill").className = "pill warn";
      $("counterPill").textContent = "counter \u2014";
      $("tipPre").textContent = "\u2014";
      $("tipTwice").textContent = "\u2014";
      return;
    }
    $("statusPill").textContent = "registered on node";
    $("statusPill").className = "pill ok";
    $("counterPill").textContent = "counter " + tip.counter;
    $("tipPre").textContent = tip.pre || "\u2014";
    $("tipTwice").textContent = tip.twice || "\u2014";
    if (tip.pre) saveAuth({ nextPasswordHash: tip.pre });
  } catch (e) {
    $("statusPill").textContent = "unreachable";
    $("statusPill").className = "pill bad";
    alertMsg(e instanceof Error ? e.message : String(e), "error");
  }
}
async function main() {
  applyTheme(resolveTheme({ preset: "dark", user: { mode: "dark" } }));
  $("siteId").textContent = siteId();
  $("nodeUrl").value = localStorage.getItem(NODE_KEY) || "";
  $("username").value = localStorage.getItem(USER_KEY) || "";
  $("registerBtn").addEventListener("click", () => void startBridge("register"));
  $("signinBtn").addEventListener("click", () => void startBridge("signin"));
  $("statusBtn").addEventListener("click", () => void startBridge("status"));
  $("cancelBtn").addEventListener("click", () => pollAbort?.abort());
  $("refreshBtn").addEventListener("click", () => {
    alertMsg("");
    void refreshTip();
  });
  await refreshTip();
}
void main();
/*! Bundled license information:

@capacitor/core/dist/index.js:
  (*! Capacitor: https://capacitorjs.com/ - MIT License *)

@scure/bip39/esm/index.js:
  (*! scure-bip39 - MIT License (c) 2022 Patricio Palladino, Paul Miller (paulmillr.com) *)
*/
//# sourceMappingURL=main.js.map
