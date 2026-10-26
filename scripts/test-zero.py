#!/usr/bin/env python3
"""Run the actual startup/manual/automatic zero functions against a fake HX711.
Requires a native g++ compiler. No device, network or account access.
"""
from pathlib import Path
import importlib.util
import os
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inventory', ROOT/'scripts/test-inventory.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)

SHIM = r'''
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>
using std::isfinite;
class String: public std::string {
public:
 String():std::string(){} String(const char* s):std::string(s){}
 String(const std::string& s):std::string(s){} String(long n):std::string(std::to_string(n)){}
 String(float n,int p){char b[80];snprintf(b,sizeof(b),"%.*f",p,n);assign(b);}
 bool isEmpty()const{return empty();}
};
uint32_t nowMs=1000;
uint32_t millis(){return nowMs;}
void delay(int){}
std::vector<String> logs;
void netLog(const String& s){logs.push_back(s);}
struct Scale {
 long offset=10000,adc=10000;float factor=100;int writes=0,reads=0,failAt=-1;
 void begin(int,int){} void set_scale(float f){factor=f;} float get_scale(){return factor;}
 long get_offset(){return offset;} void set_offset(long n){offset=n;writes++;}
 bool wait_ready_timeout(int,int){return reads!=failAt;} long read(){reads++;return adc;}
}scale;
struct {float saved=10000;int writes=0;void begin(const char*,bool){} void end(){}
 float getFloat(const char*,float){return saved;} void putFloat(const char*,float f){saved=f;writes++;}
}prefs;
struct {template<typename... A>void printf(const char*,A...) {}}Serial;
void bootProgress(int,const char*){} void displayMessage(const char*,const char*){}
const char* t(int){return "Zero Scale required";}
const int HX711_DOUT=1,HX711_SCK=2,I18N_ZERO_REQUIRED=0;
float calibrationFactor=100;bool gBootComplete=false;
const int WF_IDLE=0,OLED_STATE_AUTOTARE=1;
const float SCAN_START_WEIGHT_G=20;
bool gZeroRequired=false,autoTarePending=false;
bool gBlankFlowActive=false,gInventoryAssignmentPending=false,gBambuPending=false;
int wfPhase=WF_IDLE,currentOledState=0,filterResets=0;
long gZeroAnchorOffset=10000;
uint32_t autoTareStableSinceMs=0,lastIdleAutoTareMs=0,gZeroSampleMs=0;
uint32_t gBlankLoadSampleMs=0,gAutoTareCount=0,oledStateChangeMs=0;
float gBlankLoadSampleWeight=NAN,currentWeight=0,gZeroMin=0,gZeroMax=0,gZeroSum=0;
uint16_t gZeroSamples=0;uint8_t gZeroWindowMode=0;
String lastUID,lastUID2,gReaderTagUid[2];
void resetWeightFilters(){filterResets++;}
'''

TESTS = r'''
void reset(){
 scale=Scale();prefs.saved=10000;prefs.writes=0;nowMs=1000;calibrationFactor=100;
 gZeroRequired=autoTarePending=gBlankFlowActive=gInventoryAssignmentPending=gBambuPending=false;
 wfPhase=WF_IDLE;lastUID=lastUID2=gReaderTagUid[0]=gReaderTagUid[1]="";
 gZeroAnchorOffset=10000;autoTareStableSinceMs=lastIdleAutoTareMs=gZeroSampleMs=0;
 gZeroSamples=gZeroWindowMode=0;gBlankLoadSampleMs=0;gAutoTareCount=filterResets=0;logs.clear();
}
bool sample(float raw){nowMs+=100;gBlankLoadSampleMs=nowMs;gBlankLoadSampleWeight=raw;return processAutoTare(900);}
void steady(float raw,int n=32){for(int i=0;i<n;i++)sample(raw);}
int main(){int checks=0;
#define CHECK(x) do{if(!(x)){printf("FAIL line %d: %s\n",__LINE__,#x);return 1;}checks++;}while(0)
 // Both calibration polarities: bounded drift, never the filtered display.
 for(int sign:{-1,1}){
  reset();scale.factor=sign*100;steady(1.5f);
  CHECK(scale.offset==10000+sign*150);CHECK(gAutoTareCount==1);CHECK(!gZeroRequired);
  CHECK(prefs.writes==0);CHECK(filterResets==1);CHECK(gZeroAnchorOffset==10000);
  steady(-1.0f);CHECK(gAutoTareCount==1); // cooldown
  nowMs+=30000;steady(-1.0f);CHECK(scale.offset==10000+sign*50);CHECK(gAutoTareCount==2);
 }
 reset();steady(0.3f);CHECK(scale.writes==0);CHECK(!gZeroRequired);
 reset();steady(-150);CHECK(gZeroRequired);CHECK(scale.offset==10000);CHECK(scale.writes==0);
 reset();steady(4);CHECK(gZeroRequired);CHECK(scale.writes==0);
 reset();steady(600);CHECK(!gZeroRequired);CHECK(scale.writes==0); // real load
 reset();wfPhase=4;steady(-100);CHECK(gZeroRequired);CHECK(scale.writes==0);
 for(int guard=0;guard<6;guard++){
  reset();if(guard==0)lastUID="tag";if(guard==1)gReaderTagUid[1]="tag";
  if(guard==2)gBlankFlowActive=true;if(guard==3)gInventoryAssignmentPending=true;
  if(guard==4)gBambuPending=true;if(guard==5)wfPhase=4;
  steady(1);CHECK(scale.writes==0);CHECK(!gZeroRequired);
 }
 reset();for(int i=0;i<100;i++)sample(i%2?1.8f:0.5f);CHECK(scale.writes==0);
 reset();steady(1,20);nowMs+=1000;steady(1,20);CHECK(scale.writes==0);
 steady(1,12);CHECK(scale.writes==1); // restart stability after missing samples
 reset();sample(1);for(int i=0;i<100;i++){nowMs+=100;processAutoTare(0);}
 CHECK(scale.writes==0);CHECK(!gZeroRequired); // no reuse of a held sample
 reset();steady(NAN);CHECK(scale.writes==0);CHECK(!gZeroRequired);
 reset();steady(2);nowMs+=31000;steady(2);nowMs+=31000;steady(2);
 CHECK(gZeroRequired);CHECK(scale.offset==10400);CHECK(gAutoTareCount==2); // total cap
 reset();steady(-120);scale.adc=9500;CHECK(zeroScale("button"));
 CHECK(!gZeroRequired);CHECK(scale.offset==9500);CHECK(gZeroAnchorOffset==9500);
 CHECK(prefs.saved==9500&&prefs.writes==1);CHECK(filterResets==1);CHECK(!gBlankLoadSampleMs);
 CHECK(logs.back().find("reason=button")!=std::string::npos);
 reset();scale.failAt=4;CHECK(!zeroScale("web"));CHECK(gZeroRequired);
 CHECK(scale.offset==10000&&prefs.writes==0); // failed sample set cannot change zero
 reset();scale.adc=70000;setupScale();CHECK(scale.offset==10000);CHECK(scale.reads==0);
 CHECK(!gZeroRequired);CHECK(gZeroAnchorOffset==10000); // restart with a spool
 for(float saved:{0.f,-1.f,float(INFINITY),float(NAN),9000000.f}){
  reset();prefs.saved=saved;setupScale();CHECK(gZeroRequired);CHECK(scale.reads==0);CHECK(scale.writes==0);
 }
 printf("PASS: %d zero baseline and drift checks\n",checks);
}
'''

def main():
    cxx = os.environ.get('CXX') or shutil.which('g++')
    if not cxx:
        candidate = Path.home()/'.platformio/packages/toolchain-gccmingw32/bin/g++.exe'
        if candidate.exists():
            cxx = str(candidate)
    if not cxx:
        raise SystemExit('g++ not found; set CXX to a native C++ compiler.')
    constants = ''.join(line for line in inventory.SOURCE.read_text(encoding='utf-8').splitlines(True)
                        if re.match(r'const (float|uint32_t)\s+AUTO_TARE_', line))
    code = SHIM + constants + ''.join(inventory.extract(s) for s in
            ['void setupScale(', 'static bool zeroScale(', 'bool processAutoTare(']) + TESTS
    env = os.environ.copy()
    env['PATH'] = str(Path(cxx).parent) + os.pathsep + env.get('PATH', '')
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True, prefix='tigerscale-zero-') as folder:
        cpp = Path(folder)/'zero.cpp'
        exe = Path(folder)/('zero.exe' if os.name=='nt' else 'zero')
        cpp.write_text(code, encoding='utf-8')
        subprocess.run([cxx, '-std=c++11', *(['-static'] if os.name=='nt' else []),
                        str(cpp), '-o', str(exe)], check=True, env=env)
        subprocess.run([str(exe)], check=True, env=env)

if __name__ == '__main__':
    main()
