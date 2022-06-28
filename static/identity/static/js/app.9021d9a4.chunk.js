(this["webpackJsonp"] = this["webpackJsonp"] || []).push([[0],{

/***/ 1000:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 1007:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 1008:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 242:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 507:
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
/* harmony export (binding) */ __webpack_require__.d(__webpack_exports__, "a", function() { return App; });
/* harmony import */ var _babel_runtime_helpers_defineProperty__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(5);
/* harmony import */ var _babel_runtime_helpers_defineProperty__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(_babel_runtime_helpers_defineProperty__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(1);
/* harmony import */ var _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default = /*#__PURE__*/__webpack_require__.n(_babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1__);
/* harmony import */ var _babel_runtime_helpers_classCallCheck__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(11);
/* harmony import */ var _babel_runtime_helpers_classCallCheck__WEBPACK_IMPORTED_MODULE_2___default = /*#__PURE__*/__webpack_require__.n(_babel_runtime_helpers_classCallCheck__WEBPACK_IMPORTED_MODULE_2__);
/* harmony import */ var _babel_runtime_helpers_createClass__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(16);
/* harmony import */ var _babel_runtime_helpers_createClass__WEBPACK_IMPORTED_MODULE_3___default = /*#__PURE__*/__webpack_require__.n(_babel_runtime_helpers_createClass__WEBPACK_IMPORTED_MODULE_3__);
/* harmony import */ var _babel_runtime_helpers_inherits__WEBPACK_IMPORTED_MODULE_4__ = __webpack_require__(14);
/* harmony import */ var _babel_runtime_helpers_inherits__WEBPACK_IMPORTED_MODULE_4___default = /*#__PURE__*/__webpack_require__.n(_babel_runtime_helpers_inherits__WEBPACK_IMPORTED_MODULE_4__);
/* harmony import */ var _babel_runtime_helpers_possibleConstructorReturn__WEBPACK_IMPORTED_MODULE_5__ = __webpack_require__(15);
/* harmony import */ var _babel_runtime_helpers_possibleConstructorReturn__WEBPACK_IMPORTED_MODULE_5___default = /*#__PURE__*/__webpack_require__.n(_babel_runtime_helpers_possibleConstructorReturn__WEBPACK_IMPORTED_MODULE_5__);
/* harmony import */ var _babel_runtime_helpers_getPrototypeOf__WEBPACK_IMPORTED_MODULE_6__ = __webpack_require__(7);
/* harmony import */ var _babel_runtime_helpers_getPrototypeOf__WEBPACK_IMPORTED_MODULE_6___default = /*#__PURE__*/__webpack_require__.n(_babel_runtime_helpers_getPrototypeOf__WEBPACK_IMPORTED_MODULE_6__);
/* harmony import */ var expo_status_bar__WEBPACK_IMPORTED_MODULE_7__ = __webpack_require__(543);
/* harmony import */ var react__WEBPACK_IMPORTED_MODULE_8__ = __webpack_require__(0);
/* harmony import */ var react__WEBPACK_IMPORTED_MODULE_8___default = /*#__PURE__*/__webpack_require__.n(react__WEBPACK_IMPORTED_MODULE_8__);
/* harmony import */ var react_native_web_dist_exports_StyleSheet__WEBPACK_IMPORTED_MODULE_9__ = __webpack_require__(2);
/* harmony import */ var react_native_web_dist_exports_Text__WEBPACK_IMPORTED_MODULE_10__ = __webpack_require__(31);
/* harmony import */ var react_native_web_dist_exports_View__WEBPACK_IMPORTED_MODULE_11__ = __webpack_require__(3);
/* harmony import */ var react_native_web_dist_exports_Image__WEBPACK_IMPORTED_MODULE_12__ = __webpack_require__(86);
/* harmony import */ var react_native_paper__WEBPACK_IMPORTED_MODULE_13__ = __webpack_require__(316);
/* harmony import */ var react_native_paper__WEBPACK_IMPORTED_MODULE_14__ = __webpack_require__(88);
/* harmony import */ var react_native_paper__WEBPACK_IMPORTED_MODULE_15__ = __webpack_require__(317);
/* harmony import */ var react_native_paper__WEBPACK_IMPORTED_MODULE_16__ = __webpack_require__(79);
/* harmony import */ var react_native_paper__WEBPACK_IMPORTED_MODULE_17__ = __webpack_require__(175);
/* harmony import */ var react_native_paper__WEBPACK_IMPORTED_MODULE_18__ = __webpack_require__(315);
/* harmony import */ var expo_linking__WEBPACK_IMPORTED_MODULE_19__ = __webpack_require__(1031);
/* harmony import */ var centeridentity_expo__WEBPACK_IMPORTED_MODULE_20__ = __webpack_require__(325);
/* harmony import */ var centeridentity__WEBPACK_IMPORTED_MODULE_21__ = __webpack_require__(542);
/* harmony import */ var centeridentity__WEBPACK_IMPORTED_MODULE_21___default = /*#__PURE__*/__webpack_require__.n(centeridentity__WEBPACK_IMPORTED_MODULE_21__);
/* harmony import */ var yadacoinjs__WEBPACK_IMPORTED_MODULE_22__ = __webpack_require__(148);
/* harmony import */ var yadacoinjs__WEBPACK_IMPORTED_MODULE_22___default = /*#__PURE__*/__webpack_require__.n(yadacoinjs__WEBPACK_IMPORTED_MODULE_22__);
function ownKeys(object,enumerableOnly){var keys=Object.keys(object);if(Object.getOwnPropertySymbols){var symbols=Object.getOwnPropertySymbols(object);if(enumerableOnly)symbols=symbols.filter(function(sym){return Object.getOwnPropertyDescriptor(object,sym).enumerable;});keys.push.apply(keys,symbols);}return keys;}function _objectSpread(target){for(var i=1;i<arguments.length;i++){var source=arguments[i]!=null?arguments[i]:{};if(i%2){ownKeys(Object(source),true).forEach(function(key){_babel_runtime_helpers_defineProperty__WEBPACK_IMPORTED_MODULE_0___default()(target,key,source[key]);});}else if(Object.getOwnPropertyDescriptors){Object.defineProperties(target,Object.getOwnPropertyDescriptors(source));}else{ownKeys(Object(source)).forEach(function(key){Object.defineProperty(target,key,Object.getOwnPropertyDescriptor(source,key));});}}return target;}function _createSuper(Derived){var hasNativeReflectConstruct=_isNativeReflectConstruct();return function _createSuperInternal(){var Super=_babel_runtime_helpers_getPrototypeOf__WEBPACK_IMPORTED_MODULE_6___default()(Derived),result;if(hasNativeReflectConstruct){var NewTarget=_babel_runtime_helpers_getPrototypeOf__WEBPACK_IMPORTED_MODULE_6___default()(this).constructor;result=Reflect.construct(Super,arguments,NewTarget);}else{result=Super.apply(this,arguments);}return _babel_runtime_helpers_possibleConstructorReturn__WEBPACK_IMPORTED_MODULE_5___default()(this,result);};}function _isNativeReflectConstruct(){if(typeof Reflect==="undefined"||!Reflect.construct)return false;if(Reflect.construct.sham)return false;if(typeof Proxy==="function")return true;try{Date.prototype.toString.call(Reflect.construct(Date,[],function(){}));return true;}catch(e){return false;}}var App=function(_React$Component){_babel_runtime_helpers_inherits__WEBPACK_IMPORTED_MODULE_4___default()(App,_React$Component);var _super=_createSuper(App);function App(props){var _this$state$message,_this$state$message2;var _this;_babel_runtime_helpers_classCallCheck__WEBPACK_IMPORTED_MODULE_2___default()(this,App);_this=_super.call(this,props);_this.selectIdentity=function _callee(identity){var result;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.async(function _callee$(_context){while(1){switch(_context.prev=_context.next){case 0:_this.setState({selectedIdentity:identity});result={identity:_this.state.ci.toObject(identity)};if(!(_this.state.method==='getgraph')){_context.next=8;break;}_context.next=5;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.graph.refreshFriendsAndGroups());case 5:result.graph=_this.state.graph.graph;_context.next=45;break;case 8:if(!(_this.state.method==='groups')){_context.next=11;break;}_context.next=45;break;case 11:if(!(_this.state.method==='identity')){_context.next=14;break;}_context.next=45;break;case 14:if(!(_this.state.method==='addcontact')){_context.next=20;break;}_context.next=17;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.graph.addFriend(_this.state.message.contact));case 17:result.graph=_this.state.graph.graph;_context.next=45;break;case 20:if(!(_this.state.method==='addgroup')){_context.next=26;break;}_context.next=23;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.graph.addGroup(_this.state.message.group));case 23:result.graph=_this.state.graph.graph;_context.next=45;break;case 26:if(!(_this.state.method==='collection')){_context.next=32;break;}_context.next=29;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.graph.refreshFriendsAndGroups());case 29:result.graph=_this.state.graph.graph;_context.next=45;break;case 32:if(!(_this.state.method==='sendmail')){_context.next=39;break;}_context.next=35;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.graph.refreshFriendsAndGroups());case 35:_context.next=37;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.graph._sendMail(_this.state.message));case 37:_context.next=45;break;case 39:if(!(_this.state.method==='getmail')){_context.next=45;break;}_context.next=42;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.graph.refreshFriendsAndGroups());case 42:_context.next=44;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.graph._getMail(null,_this.state.message.collection));case 44:result.graph=_this.state.graph.graph;case 45:if(!_this.state.sign){_context.next=47;break;}return _context.abrupt("return");case 47:_this.respond(result);case 48:case"end":return _context.stop();}}},null,null,null,Promise);};_this.sign=function _callee2(){var selectedIdentity;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.async(function _callee2$(_context2){while(1){switch(_context2.prev=_context2.next){case 0:selectedIdentity=_this.state.selectedIdentity;if(selectedIdentity.key){_context2.next=5;break;}_context2.next=4;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.ci.reviveUser(selectedIdentity.wif,selectedIdentity.username));case 4:selectedIdentity=_context2.sent;case 5:_context2.t0=_this;_context2.next=8;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.ci.sign(_this.state.message.challenge,selectedIdentity));case 8:_context2.t1=_context2.sent;_context2.t2={signature:_context2.t1};_context2.t0.setState.call(_context2.t0,_context2.t2);_this.respond({identity:_this.state.ci.toObject(selectedIdentity),hash:_this.state.message.challenge,signature:_this.state.signature});case 12:case"end":return _context2.stop();}}},null,null,null,Promise);};var data={};if(window.location.hash.length>1){data=JSON.parse(atob(window.location.hash.substr(1)));}_this.state=_objectSpread({graph:new yadacoinjs__WEBPACK_IMPORTED_MODULE_22__["Graph"](),identity:new yadacoinjs__WEBPACK_IMPORTED_MODULE_22__["Identity"](),ci:new centeridentity__WEBPACK_IMPORTED_MODULE_21___default.a(undefined,'https://centeridentity.com',true),checked:true,selectIdentity:true},data);document.title=_this.state.method||'Identity Vault - Center Identity';_this.state.graph.settings=new yadacoinjs__WEBPACK_IMPORTED_MODULE_22__["Settings"]();_this.state.graph.settings.webServiceURL=window.location.origin;_this.state.graph.identity=_this.state.identity;_this.state.graph.crypt=new yadacoinjs__WEBPACK_IMPORTED_MODULE_22__["Crypt"]();_this.state.graph.crypt.identity=_this.state.graph.identity;_this.state.graph.transaction=new yadacoinjs__WEBPACK_IMPORTED_MODULE_22__["Transaction"]();_this.state.graph.transaction.crypt=_this.state.graph.crypt;_this.state.graph.transaction.identity=_this.state.graph.identity;_this.state.graph.transaction.settings=_this.state.graph.settings;_this.state.sign=['contract','signin','invite'].indexOf(_this.state.method)>-1;var identities=localStorage.getItem('identities');if(identities){identities=JSON.parse(identities);_this.state.addIdentity=false;}else{identities=[];_this.state.addIdentity=true;}_this.state.identities=identities;if((_this$state$message=_this.state.message)!=null&&_this$state$message.identity){_this.state.identities.filter(function(identity){return identity.wif;}).forEach(function _callee3(identity){return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.async(function _callee3$(_context3){while(1){switch(_context3.prev=_context3.next){case 0:if(!(_this.state.message.identity.username_signature===identity.username_signature)){_context3.next=7;break;}_this.state.staticIdentity=true;_this.state.selectedIdentity=identity;_context3.next=5;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this.state.identity.reviveUser(identity.wif,identity.username));case 5:_this.state.identity.identity=_context3.sent;_this.selectIdentity(identity);case 7:case"end":return _context3.stop();}}},null,null,null,Promise);});}if((_this$state$message2=_this.state.message)!=null&&_this$state$message2.identifier){_this.state.public_username=_this.state.message.identifier;}return _this;}_babel_runtime_helpers_createClass__WEBPACK_IMPORTED_MODULE_3___default()(App,[{key:"respond",value:function respond(result){var source;if(this.state.portal==='window'){source=window.opener||window.parent;if(source){var message={};}}else if(this.state.portal==='iframe'){source=window.parent;}if(!source)return;source.postMessage({method:this.state.method,portal:this.state.portal,result:result},this.state.origin);}},{key:"render",value:function render(){var _this$state$message3,_this$state$message4,_this2=this;console.log(centeridentity_expo__WEBPACK_IMPORTED_MODULE_20__[/* RecoverIdentity */ "a"]);var extra_args=JSON.parse(localStorage.getItem('centeridentity_extra_args')||'{}');return react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_13__[/* default */ "a"],{theme:react_native_paper__WEBPACK_IMPORTED_MODULE_14__[/* default */ "a"]},react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_View__WEBPACK_IMPORTED_MODULE_11__[/* default */ "a"],{style:styles.container},react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_Text__WEBPACK_IMPORTED_MODULE_10__[/* default */ "a"],null,react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_Image__WEBPACK_IMPORTED_MODULE_12__[/* default */ "a"],{source:{uri:"https://centeridentity.com/centeridentitystatic/center-identity-logo.png"},style:styles.logo})),!this.state.selectedIdentity&&!this.state.staticIdentity&&this.state.public_username&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_15__[/* default */ "a"],{style:styles.heading},"Create Account"),this.state.selectedIdentity&&((_this$state$message3=this.state.message)==null?void 0:_this$state$message3.challenge)&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_Text__WEBPACK_IMPORTED_MODULE_10__[/* default */ "a"],{style:styles.menuTitle},"Use the identity saved for ",react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement("strong",null,this.state.selectedIdentity.username)," to sign this message?"),this.state.selectedIdentity&&((_this$state$message4=this.state.message)==null?void 0:_this$state$message4.challenge)&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_Text__WEBPACK_IMPORTED_MODULE_10__[/* default */ "a"],null,this.state.message.challenge),this.state.error&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_Text__WEBPACK_IMPORTED_MODULE_10__[/* default */ "a"],null,this.state.error),react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(expo_status_bar__WEBPACK_IMPORTED_MODULE_7__[/* StatusBar */ "a"],{style:"auto"}),this.state.selectedIdentity&&this.state.sign&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_16__[/* default */ "a"],{onPress:function onPress(){_this2.sign();}},"Sign"),this.state.identities.length>0&&this.state.selectedIdentity&&!this.state.staticIdentity&&false&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_16__[/* default */ "a"],{onPress:function onPress(){_this2.setState({selectedIdentity:null,importIdentity:false,addIdentity:false,selectIdentity:true,exportIdentity:false});}},"Select different identity"),!this.state.selectedIdentity&&!this.state.staticIdentity&&!this.state.public_username&&false&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_16__[/* default */ "a"],{onPress:function onPress(){_this2.setState({checked:true,selectedIdentity:null,importIdentity:false,addIdentity:true,selectIdentity:false,exportIdentity:false});}},"Locate identity"),!this.state.selectedIdentity&&!this.state.staticIdentity&&!this.state.public_username&&false&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_16__[/* default */ "a"],{onPress:function onPress(){_this2.setState({checked:true,selectedIdentity:null,importIdentity:true,addIdentity:false,selectIdentity:false,exportIdentity:false});}},"Import identity"),this.state.identities.length>0&&!this.state.staticIdentity&&this.state.selectedIdentity&&false&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_16__[/* default */ "a"],{onPress:function onPress(){_this2.setState({importIdentity:false,addIdentity:false,selectIdentity:false,exportIdentity:true});}},"Export identity"),this.state.selectedIdentity&&this.state.exportIdentity&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_View__WEBPACK_IMPORTED_MODULE_11__[/* default */ "a"],null,react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_17__[/* default */ "a"],{label:"WIF",value:this.state.selectedIdentity.wif})),this.state.identities.length>0&&!this.state.selectedIdentity&&this.state.selectIdentity&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_Text__WEBPACK_IMPORTED_MODULE_10__[/* default */ "a"],{style:styles.menuTitle},"Select an identity from the list below"),this.state.identities.length>0&&!this.state.selectedIdentity&&this.state.selectIdentity&&this.state.identities.sort(function(a,b){if(a.username.toLowerCase()>b.username.toLowerCase())return 1;if(a.username.toLowerCase()<b.username.toLowerCase())return-1;return 0;}).map(function(identity){return react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_16__[/* default */ "a"],{labelStyle:styles.username,onPress:function onPress(){_this2.selectIdentity(identity);}},identity.username);}),!this.state.selectedIdentity&&this.state.addIdentity&&false&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_Text__WEBPACK_IMPORTED_MODULE_10__[/* default */ "a"],{style:styles.menuTitle},"On the map below, find an exact location which is very personal / private to you and click it twice. This will be the information you use to recover your identity."),!this.state.selectedIdentity&&this.state.importIdentity&&false&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_Text__WEBPACK_IMPORTED_MODULE_10__[/* default */ "a"],{style:styles.menuTitle},"Input your public username and WIF key below"),!this.state.selectedIdentity&&(this.state.addIdentity||this.state.importIdentity)&&false&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_18__[/* default */ "a"].Item,{label:"Remember identity?",status:this.state.checked?'checked':'unchecked',style:styles.checkbox,theme:{dark:false,fonts:{regular:{fontFamily:'Open Sans'},thin:{fontFamily:'Open Sans'},medium:{fontFamily:'Open Sans'},light:{fontFamily:'Open Sans'}}},onPress:function onPress(){_this2.setState({checked:!_this2.state.checked});}}),!this.state.selectedIdentity&&this.state.importIdentity&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_View__WEBPACK_IMPORTED_MODULE_11__[/* default */ "a"],null,react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_17__[/* default */ "a"],{label:"Username",value:this.state.public_username||this.state.username,onChangeText:function onChangeText(username){_this2.setState({username:username});}}),react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_17__[/* default */ "a"],{label:"WIF",value:this.state.wif,onChangeText:function onChangeText(wif){_this2.setState({wif:wif});}}),react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_16__[/* default */ "a"],{onPress:function _callee4(){var identity;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.async(function _callee4$(_context4){while(1){switch(_context4.prev=_context4.next){case 0:_context4.next=2;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.awrap(_this2.state.ci.reviveUser(_this2.state.wif,_this2.state.username));case 2:identity=_context4.sent;_this2.state.identities.push(identity);if(_this2.state.checked){localStorage.setItem('identities',JSON.stringify(_this2.state.identities.map(function(item){return JSON.parse(_this2.state.ci.toJson(item));})));}_this2.setState({importIdentity:false,selectIdentity:true});case 6:case"end":return _context4.stop();}}},null,null,null,Promise);}},"Confirm")),!this.state.showVideo&&false&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_16__[/* default */ "a"],{labelStyle:styles.username,onPress:function onPress(){_this2.setState({showVideo:true});}},"Help"),this.state.showVideo&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_web_dist_exports_View__WEBPACK_IMPORTED_MODULE_11__[/* default */ "a"],{style:styles.center},react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(react_native_paper__WEBPACK_IMPORTED_MODULE_16__[/* default */ "a"],{labelStyle:styles.username,onPress:function onPress(){_this2.setState({showVideo:false});}},"Close help"),react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement("iframe",{width:"560",height:"315",src:"https://www.youtube.com/embed/H69RVbxpZ0w",title:"YouTube video player",frameborder:"0",allow:"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",allowfullscreen:"allowfullscreen",allow:"fullscreen;"})),!this.state.selectedIdentity&&(this.state.addIdentity||this.state.public_username)&&react__WEBPACK_IMPORTED_MODULE_8___default.a.createElement(centeridentity_expo__WEBPACK_IMPORTED_MODULE_20__[/* RecoverIdentity */ "a"],{ci:this.state.ci,registerUrl:"/create-account",userNotFoundMessage:this.state.user_not_found_message||'Identity not found for provided username and coordinates.',publicUsername:this.state.public_username||'',publicUsernameLabel:this.state.public_username_label||'Public username',privateUsernameLabel:this.state.private_username_label||'Private username (do not share)',userNotFoundMessage:"No account found for that email address, click 'create new' to create a new account or click 'try again' to select a different location.",extraData:extra_args,onIdentity:function _callee5(identity){var result;return _babel_runtime_regenerator__WEBPACK_IMPORTED_MODULE_1___default.a.async(function _callee5$(_context5){while(1){switch(_context5.prev=_context5.next){case 0:_this2.state.identities.push(identity);if(_this2.state.checked){localStorage.setItem('identities',JSON.stringify(_this2.state.identities.map(function(item){return JSON.parse(_this2.state.ci.toJson(item));})));}_this2.setState({importIdentity:false,selectIdentity:false,selectedIdentity:identity,addIdentity:false});result={identity:_this2.state.ci.toObject(identity)};_this2.respond(result);case 5:case"end":return _context5.stop();}}},null,null,null,Promise);},createText:this.state.create_button_text||'Create new',tryAgainText:this.state.try_again_button_text||'Try again',width:"100%",height:600,clientSideOnly:true})));}}]);return App;}(react__WEBPACK_IMPORTED_MODULE_8___default.a.Component);var styles=react_native_web_dist_exports_StyleSheet__WEBPACK_IMPORTED_MODULE_9__[/* default */ "a"].create({container:{flex:1,backgroundColor:'#fff',justifyContent:'center',width:'100%',padding:25,textAlign:'center'},heading:{textAlign:'center'},center:{marginRight:'auto',marginLeft:'auto',marginBottom:25},logo:{width:'100%',height:85,maxWidth:300,resizeMode:'contain'},checkbox:{width:250,color:'black'},menuTitle:{fontSize:20,marginTop:25,marginBottom:10},username:{textTransform:'none',color:'#1bb5d7',fontWeight:'bold',fontSize:20}});

/***/ }),

/***/ 571:
/***/ (function(module, exports, __webpack_require__) {

module.exports = __webpack_require__(1032);


/***/ }),

/***/ 622:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 624:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 634:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 636:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 918:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 920:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 948:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 950:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 951:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 956:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 958:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 964:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 966:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 985:
/***/ (function(module, exports) {

/* (ignored) */

/***/ }),

/***/ 997:
/***/ (function(module, exports) {

/* (ignored) */

/***/ })

},[[571,1,2]]]);
//# sourceMappingURL=app.9021d9a4.chunk.js.map