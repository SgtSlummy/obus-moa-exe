const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const {EventEmitter} = require('node:events');

function load({healthy = [true], compatible = 405} = {}) {
  const spawned = [], events = {};
  const request = (health, callback) => {
    const req = new EventEmitter();
    req.end = () => {};
    req.destroy = () => req.emit('error', new Error('closed'));
    queueMicrotask(() => {
      const response = new EventEmitter();
      const ready = healthy.length > 1 ? healthy.shift() : healthy[0];
      response.statusCode = health ? (ready ? 200 : 503) : compatible;
      response.resume = () => {};
      callback(response);
      if (health) {
        response.emit('data', JSON.stringify({service:'obus-moa', status:ready ? 'ok' : 'starting'}));
        response.emit('end');
      }
    });
    return req;
  };
  const app = {isPackaged:false, requestSingleInstanceLock:()=>true,
    whenReady:()=>({then(){}}), on:(name, fn)=>{events[name]=fn;}};
  const context = {module:{exports:{}}, __dirname:path.resolve('electron_app'), URL,
    process:{env:{}, platform:'win32'}, console, setTimeout, clearTimeout,
    require:(name)=>{
      if (name==='electron') return {app};
      if (name==='http') return {get:(_url,_options,callback)=>request(true,callback),request:(_url,_options,callback)=>request(false,callback)};
      if (name==='child_process') return {spawn:(...args)=>{
        const child = new EventEmitter(); child.unref=()=>{child.unreferenced=true;};
        spawned.push({args,child}); return child;
      }};
      return require(name);
    }};
  vm.runInNewContext(fs.readFileSync('electron_app/main.js','utf8'), context);
  return {...context.module.exports, spawned, events};
}

(async()=>{
  let runtime = load();
  assert.equal(await runtime.ensureBackend(runtime.DEFAULT_OBUS_URL), runtime.DEFAULT_OBUS_URL);
  assert.equal(runtime.spawned.length, 0, 'healthy shared backend must be reused');
  runtime = load({compatible:404});
  await assert.rejects(runtime.ensureBackend(runtime.DEFAULT_OBUS_URL), /Update the shared OBus backend/);
  assert.equal(runtime.spawned.length, 0, 'incompatible shared backend must not create a private one');
  runtime = load({healthy:[false,true,true]});
  await runtime.ensureBackend(runtime.DEFAULT_OBUS_URL);
  assert.equal(runtime.spawned.length, 1);
  const {args,child} = runtime.spawned[0];
  assert.equal(args[2].env.OBUS_PORT, '38173');
  assert.equal(args[2].env.OBUS_HOST, '127.0.0.1');
  assert.equal(args[2].detached, true);
  assert.equal(child.unreferenced, true);
  assert.equal(runtime.events['before-quit'], undefined, 'desktop exit must not kill the shared backend');
  assert.equal(runtime.obusUrl(), runtime.DEFAULT_OBUS_URL);
  console.log('Shared backend lifecycle checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
