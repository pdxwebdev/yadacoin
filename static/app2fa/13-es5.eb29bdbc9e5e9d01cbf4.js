(window.webpackJsonp=window.webpackJsonp||[]).push([[13],{JLuJ:function(l,n,u){"use strict";u.r(n);var e=u("CcnG"),t=function(){return function(){}}(),r=u("pMnS"),i=u("oBZk"),s=u("ZZ/e"),o=u("Ip0R"),b=function(){function l(l,n){var u=this;this.http=l,this.storage=n,this.timeLeft=0,this.lastTime=0,this.auth_codes=[],this.services=[],Math.floor(Date.now()/1e3),Date.now(),setInterval((function(){var l=Date.now()/1e3;if(l>u.lastTime){var n=30*Math.floor(Date.now()/1e3/30),e=Date.now()/1e3-n;u.timeLeft=e/30;for(var t=0;t<u.services.length;t++)u.services[t].auth_code=("000000"+BigInt("0x"+forge.sha256.create().update(n+u.services[t].hashedSharedSecret).digest().toHex()).toString()).substr(-6);u.lastTime=l}}),500)}return l.prototype.ionViewDidEnter=function(){var l=this;this.services=[],this.storage.forEach((function(n,u){"storage"===u.substr(0,"storage".length)&&l.services.push(n)}))},l}(),a=u("t/Na"),c=u("iw74"),h=e.qb({encapsulation:0,styles:[[".welcome-card[_ngcontent-%COMP%]   img[_ngcontent-%COMP%]{max-height:35vh;overflow:hidden}"]],data:{}});function g(l){return e.Ib(0,[(l()(),e.sb(0,0,null,null,5,"ion-item",[],null,null,null,i.v,i.g)),e.rb(1,49152,null,0,s.E,[e.h,e.k,e.z],null,null),(l()(),e.sb(2,0,null,0,1,"ion-label",[],[[8,"innerHTML",1]],null,null,i.w,i.h)),e.rb(3,49152,null,0,s.K,[e.h,e.k,e.z],null,null),(l()(),e.sb(4,0,null,0,1,"ion-label",[],[[8,"innerHTML",1]],null,null,i.w,i.h)),e.rb(5,49152,null,0,s.K,[e.h,e.k,e.z],null,null)],null,(function(l,n){var u=n.component;l(n,2,0,u.services[n.context.index].service.substr("storage-".length)),l(n,4,0,u.services[n.context.index].auth_code)}))}function f(l){return e.Ib(0,[(l()(),e.sb(0,0,null,null,1,"div",[],null,null,null,null,null)),(l()(),e.Hb(-1,null,["No services. Add services on the settings tab."]))],null,null)}function v(l){return e.Ib(0,[(l()(),e.sb(0,0,null,null,6,"ion-header",[],null,null,null,i.s,i.d)),e.rb(1,49152,null,0,s.y,[e.h,e.k,e.z],null,null),(l()(),e.sb(2,0,null,0,4,"ion-toolbar",[],null,null,null,i.D,i.o)),e.rb(3,49152,null,0,s.zb,[e.h,e.k,e.z],null,null),(l()(),e.sb(4,0,null,0,2,"ion-title",[],null,null,null,i.C,i.n)),e.rb(5,49152,null,0,s.xb,[e.h,e.k,e.z],null,null),(l()(),e.Hb(-1,0,[" Yada 2FA "])),(l()(),e.sb(7,0,null,null,20,"ion-content",[],null,null,null,i.r,i.c)),e.rb(8,49152,null,0,s.r,[e.h,e.k,e.z],null,null),(l()(),e.sb(9,0,null,0,18,"div",[["class","ion-padding"]],null,null,null,null,null)),(l()(),e.sb(10,0,null,null,1,"ion-progress-bar",[],null,null,null,i.y,i.j)),e.rb(11,49152,null,0,s.W,[e.h,e.k,e.z],{value:[0,"value"]},null),(l()(),e.sb(12,0,null,null,13,"ion-list",[],null,null,null,i.x,i.i)),e.rb(13,49152,null,0,s.L,[e.h,e.k,e.z],null,null),(l()(),e.sb(14,0,null,0,9,"ion-item",[],null,null,null,i.v,i.g)),e.rb(15,49152,null,0,s.E,[e.h,e.k,e.z],null,null),(l()(),e.sb(16,0,null,0,3,"ion-label",[],null,null,null,i.w,i.h)),e.rb(17,49152,null,0,s.K,[e.h,e.k,e.z],null,null),(l()(),e.sb(18,0,null,0,1,"strong",[],null,null,null,null,null)),(l()(),e.Hb(-1,null,["Service name"])),(l()(),e.sb(20,0,null,0,3,"ion-label",[],null,null,null,i.w,i.h)),e.rb(21,49152,null,0,s.K,[e.h,e.k,e.z],null,null),(l()(),e.sb(22,0,null,0,1,"strong",[],null,null,null,null,null)),(l()(),e.Hb(-1,null,["Authorization code"])),(l()(),e.hb(16777216,null,0,1,null,g)),e.rb(25,278528,null,0,o.h,[e.N,e.K,e.s],{ngForOf:[0,"ngForOf"]},null),(l()(),e.hb(16777216,null,null,1,null,f)),e.rb(27,16384,null,0,o.i,[e.N,e.K],{ngIf:[0,"ngIf"]},null)],(function(l,n){var u=n.component;l(n,11,0,u.timeLeft),l(n,25,0,u.services),l(n,27,0,u.services.length<=0)}),null)}function d(l){return e.Ib(0,[(l()(),e.sb(0,0,null,null,1,"app-tab1",[],null,null,null,v,h)),e.rb(1,49152,null,0,b,[a.c,c.b],null,null)],null,null)}var p=e.ob("app-tab1",b,d,{},{},[]),w=u("gIcY"),k=u("ZYCi");u.d(n,"Tab1PageModuleNgFactory",(function(){return B}));var B=e.pb(t,[],(function(l){return e.Ab([e.Bb(512,e.j,e.ab,[[8,[r.a,p]],[3,e.j],e.x]),e.Bb(4608,o.k,o.j,[e.u,[2,o.q]]),e.Bb(4608,s.a,s.a,[e.z,e.g]),e.Bb(4608,s.Db,s.Db,[s.a,e.j,e.q]),e.Bb(4608,s.Gb,s.Gb,[s.a,e.j,e.q]),e.Bb(4608,w.g,w.g,[]),e.Bb(1073742336,o.b,o.b,[]),e.Bb(1073742336,s.Bb,s.Bb,[]),e.Bb(1073742336,w.f,w.f,[]),e.Bb(1073742336,w.a,w.a,[]),e.Bb(1073742336,k.n,k.n,[[2,k.s],[2,k.m]]),e.Bb(1073742336,t,t,[]),e.Bb(1024,k.k,(function(){return[[{path:"",component:b}]]}),[])])}))}}]);