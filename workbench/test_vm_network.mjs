import test from 'node:test';
import assert from 'node:assert/strict';
import {discoverVmBind} from './vm_network.mjs';

test('discovers the exact Hyper-V Default Switch private IPv4 address',()=>{
 assert.equal(discoverVmBind({WLAN:[{family:'IPv4',address:'192.168.3.6',internal:false}], 'vEthernet (Default Switch)':[ {family:'IPv6',address:'fe80::1',internal:false},{family:'IPv4',address:'172.20.0.1',internal:false}]}),'172.20.0.1');
});

test('rejects a missing, public, or ambiguous Default Switch address',()=>{
 assert.throws(()=>discoverVmBind({WLAN:[{family:'IPv4',address:'192.168.3.6',internal:false}]}));
 assert.throws(()=>discoverVmBind({'vEthernet (Default Switch)':[ {family:'IPv4',address:'8.8.8.8',internal:false}]}));
 assert.throws(()=>discoverVmBind({'vEthernet (Default Switch)':[ {family:'IPv4',address:'172.20.0.1',internal:false},{family:'IPv4',address:'172.20.0.2',internal:false}]}));
});

