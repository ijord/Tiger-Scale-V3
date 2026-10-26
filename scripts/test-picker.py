#!/usr/bin/env python3
"""Exercise the firmware picker against real native LVGL, without a device.
Requires the installed PlatformIO LVGL sources and a native gcc/g++ compiler.
Run from the repository: python scripts/test-picker.py
"""
from pathlib import Path
import concurrent.futures, subprocess, os, importlib.util, re, shutil, hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.pio/picker-native';OUT.mkdir(exist_ok=True)
LV=next((ROOT/'.pio/libdeps').glob('*/lvgl'),None)
if not LV: raise SystemExit('Build a PlatformIO environment first to install LVGL.')
BIN=Path.home()/'.platformio/packages/toolchain-gccmingw32/bin'
CXX=os.environ.get('CXX') or shutil.which('g++') or str(BIN/'g++.exe')
CC=os.environ.get('CC') or shutil.which('gcc') or str(BIN/'gcc.exe')
env=os.environ.copy();env['PATH']=str(Path(CXX).parent)+os.pathsep+env['PATH']
flags=['-DLV_CONF_SKIP=1','-DLV_USE_LARGE_COORD=1','-DLV_MEM_SIZE=1048576','-DLV_COLOR_DEPTH=16','-DLV_FONT_MONTSERRAT_20=1','-DLV_FONT_MONTSERRAT_28=1','-I'+str(LV)]
OUT=OUT/hashlib.sha256(str(flags).encode()).hexdigest()[:12];OUT.mkdir(exist_ok=True)
latest=max(p.stat().st_mtime for p in LV.joinpath('src').rglob('*') if p.suffix in ('.c','.h'))
def compile_c(p):
 o=OUT/(str(p.relative_to(LV)).replace('\\','_').replace('/','_')+'.o')
 if not o.exists() or o.stat().st_mtime < latest: subprocess.run([CC,'-std=c99','-w',*flags,'-c',str(p),'-o',str(o)],env=env,check=True,capture_output=True)
 return o
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool: objs=list(pool.map(compile_c,LV.joinpath('src').rglob('*.c')))
spec=importlib.util.spec_from_file_location('inventory',ROOT/'scripts/test-inventory.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
funcs=''.join(m.extract(x) for x in ['static lv_obj_t* lvglAddHeader(', 'static bool inventoryWait(', 'struct InventorySpool {','struct InventoryPicker {','static void inventoryColor(','static bool inventoryColorLess(','static lv_obj_t* inventoryLabel(','static bool selectSpoolContainer(','static bool inventoryMatches(','static void inventoryPickerRefresh(','static void inventoryPickerFilter(','static void inventoryPickerEvent(','static void inventoryPickMaterial(','static int inventoryPickSpool('])
funcs=funcs.replace('    while (!p.exit && !gBlankFlowRemoved) {','    testPicker(&p); p.exit=pickerMode != 1;\n    while (!p.exit && !gBlankFlowRemoved) {')
funcs=funcs.replace('        while (selection.index < 0 && !selection.exit && !gBlankFlowRemoved) {','        testContainerScreen();\n        while (selection.index < 0 && !selection.exit && !gBlankFlowRemoved) {')
funcs=funcs.replace('    while (!exit && chosen < 0 && !gBlankFlowRemoved) {','    testMaterialScreen();\n    while (!exit && chosen < 0 && !gBlankFlowRemoved) {')
keys=sorted(set(re.findall(r'I18N_[A-Z_]+',funcs)))
shim=r'''
#include <lvgl.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
class String:public std::string{public:String(){}using std::string::string;String(const std::string& s):std::string(s){}String(float n,int){char b[40];snprintf(b,sizeof(b),"%.0f",n);assign(b);}bool isEmpty()const{return empty();}bool equalsIgnoreCase(const String& s)const{return strcasecmp(c_str(),s.c_str())==0;}};
const lv_font_t&gFont14=lv_font_montserrat_14;
const lv_font_t&gFont20=lv_font_montserrat_20;
#define LVCOL_BG lv_color_hex(0x080C0F)
#define LVCOL_TEXT lv_color_white()
#define LVCOL_ACCENT lv_color_hex(0x2196F3)
#define LVCOL_BORDER lv_color_hex(0x273442)
#define LVCOL_CARD lv_color_hex(0x101820)
bool gBlankFlowRemoved=false;
bool gBlankFlowActive=false,gBlankLoadLatched=false,gBlankLoadWasPresent=false;
uint32_t gBlankEmptySinceMs=0;
int containerMode=0,containerSaves=0,containerScreens=0,containerNotices=0;
bool containerKnown=false,containerFailure=false;
int pickerMode=0,pickerTicks=0,confirmationDialogs=0;
const char* t(int){return "Label";}
using LangKey=int;
struct SpoolContainer{String id,label,type;uint16_t brand=0;float weight=0;};
struct InventoryRequest{enum{LIST,CONTAINERS,SET_CONTAINER}op=LIST;std::vector<SpoolContainer> containers;String containerId;float containerWeight=0;int error=0;bool done=false,cancel=false,ok=false;};
InventoryRequest* gInventoryRequest=nullptr;int requestTicks=0;
void blankFlowTick(){lv_tick_inc(16);if(pickerMode==1&&++pickerTicks==2)gBlankFlowRemoved=true;if(gInventoryRequest&&++requestTicks%3==0){auto r=gInventoryRequest;if(r->op==InventoryRequest::CONTAINERS){if(containerKnown){r->containerId="known";r->containerWeight=250;}else for(int i=0;i<55;i++){SpoolContainer c;c.id="box"+std::to_string(i);c.label="Spool "+std::to_string(i);c.weight=200+i;r->containers.push_back(c);}}if(r->op==InventoryRequest::SET_CONTAINER)containerSaves++;r->ok=!containerFailure;r->done=true;gInventoryRequest=nullptr;}}
void lvglNotice(const char*){containerNotices++;}
void testContainerScreen();
void testMaterialScreen();int materialChoice=0;
lv_obj_t* lvglCenteredScreen(lv_obj_t** col){lv_obj_t* scr=lv_obj_create(nullptr);*col=scr;return scr;}
void lvglAddSpinner(lv_obj_t* p){lv_spinner_create(p,1000,60);}
void lvglAddCenteredLabel(lv_obj_t* p,const char* text,lv_color_t,const lv_font_t*){lv_obj_t* label=lv_label_create(p);lv_label_set_text(label,text);}
lv_obj_t* transitionHome=nullptr;int homeFlushes=0;
uint32_t millis(){return lv_tick_get();}
void delay(int n){lv_tick_inc(n);}
bool tsRead(int16_t&,int16_t&){return false;}
bool lvglAskYesNo(const char*,const char*){confirmationDialogs++;return false;}

struct InventoryPicker;void testPicker(InventoryPicker*);
static lv_point_t touchPoint;static bool pressed=false;
void input(lv_indev_drv_t*,lv_indev_data_t* d){d->point=touchPoint;d->state=pressed?LV_INDEV_STATE_PRESSED:LV_INDEV_STATE_RELEASED;}
void pump(int n=20){for(int i=0;i<n;i++){lv_tick_inc(16);lv_timer_handler();}}
void touch(int x,int y){touchPoint={x,y};pressed=true;pump(5);pressed=false;pump();}
'''
tail=r'''
static int checks=0;
#define CHECK(x) do{if(!(x)){printf("FAIL line %d: %s\n",__LINE__,#x);exit(1);}checks++;}while(0)
void testMaterialScreen(){
 pump();lv_obj_t* list=lv_obj_get_child(lv_scr_act(),-1);
 CHECK(lv_obj_get_child_cnt(list)==3);
 CHECK(!strcmp(lv_list_get_btn_text(list,lv_obj_get_child(list,1)),"PETG"));
 CHECK(!strcmp(lv_list_get_btn_text(list,lv_obj_get_child(list,2)),"PLA"));
 if(materialChoice<0)touch(40,24);
 else lv_event_send(lv_obj_get_child(list,materialChoice),LV_EVENT_CLICKED,nullptr);
}
void testContainerScreen(){
 containerScreens++;pump();CHECK(gBlankFlowActive&&gBlankLoadLatched);
 lv_obj_t* list=lv_obj_get_child(lv_scr_act(),-1);CHECK(lv_obj_get_child_cnt(list)==55);
 if(containerMode==2)touch(40,24);
 else if(containerMode==3)gBlankFlowRemoved=true;
 else touch(220,90);
}
void testPicker(InventoryPicker* p){
 if(pickerMode){
  pump();
  for(int i=0;i<5;i++)if(p->indices[i]==0)lv_event_send(p->cards[i],LV_EVENT_CLICKED,nullptr);
  CHECK(p->selected==0&&!p->choose);
  if(pickerMode==1){lv_event_send(p->accept,LV_EVENT_CLICKED,nullptr);CHECK(p->choose);}
  return;
 }
 pump();CHECK(p->axis==0&&p->visible.size()==p->spools->size());
 CHECK(lv_obj_get_style_bg_opa(p->bwSlider,LV_PART_KNOB)==LV_OPA_TRANSP);
 CHECK(lv_obj_get_style_bg_opa(p->slider,LV_PART_KNOB)==LV_OPA_TRANSP);
 lv_point_t pt{160,234};CHECK(lv_indev_search_obj(lv_scr_act(),&pt)==p->bwSlider);
 touch(160,234);CHECK(p->axis==1&&lv_slider_get_value(p->bwSlider)>=48&&lv_slider_get_value(p->bwSlider)<=50);
 for(int index:p->visible)CHECK((*p->spools)[index].saturation<.15f);
 CHECK(lv_obj_get_style_bg_opa(p->slider,LV_PART_KNOB)==LV_OPA_TRANSP);
 CHECK(lv_obj_get_style_bg_opa(p->bwSlider,LV_PART_KNOB)==LV_OPA_COVER);
 touch(210,286);CHECK(p->axis==2&&lv_slider_get_value(p->slider)>=236&&lv_slider_get_value(p->slider)<=238);
 for(int index:p->visible)CHECK((*p->spools)[index].saturation>=.15f);
 CHECK(lv_obj_get_style_bg_opa(p->bwSlider,LV_PART_KNOB)==LV_OPA_TRANSP);
 touch(308,286);CHECK(lv_slider_get_value(p->slider)==359);
 CHECK(lv_obj_get_scroll_x(p->row)==(int)p->visible.size()*174); // red wraps to the first hue
 int count=p->visible.size();
 lv_obj_scroll_to_x(p->row,(count+3)*174,LV_ANIM_OFF);pump();
 CHECK(lv_slider_get_value(p->slider)==lroundf((*p->spools)[p->visible[3]].hue));
 lv_obj_scroll_to_x(p->row,(2*count+1)*174,LV_ANIM_OFF);pump();
 CHECK(lv_obj_get_scroll_x(p->row)==(count+1)*174);
 lv_obj_scroll_to_x(p->row,(count-1)*174,LV_ANIM_OFF);pump();
 CHECK(lv_obj_get_scroll_x(p->row)==(2*count-1)*174);
 int position=2*count-1,slot=position%5;
 CHECK(p->indices[slot]==p->visible[count-1]);
 lv_event_send(p->cards[slot],LV_EVENT_CLICKED,nullptr);CHECK(p->selected==p->visible[count-1]);
 p->material="PLA";inventoryPickerFilter(p);pump();
 CHECK(!p->visible.empty()&&p->selected==-1&&lv_obj_has_state(p->accept,LV_STATE_DISABLED));
 for(int index:p->visible)CHECK((*p->spools)[index].material=="PLA"&&(*p->spools)[index].saturation>=.15f);
 // Choosing a material clears either active color filter and both markers.
 for(int axis:{1,2}){
  p->axis=axis;lv_slider_set_value(p->bwSlider,60,LV_ANIM_OFF);lv_slider_set_value(p->slider,240,LV_ANIM_OFF);
  materialChoice=axis;inventoryPickMaterial(p);pump();
  CHECK(p->material==(axis==1?"PETG":"PLA")&&p->axis==0&&p->selected==-1);
  CHECK(lv_slider_get_value(p->bwSlider)==0&&lv_slider_get_value(p->slider)==0);
  CHECK(lv_obj_get_style_bg_opa(p->bwSlider,LV_PART_KNOB)==LV_OPA_TRANSP&&lv_obj_get_style_bg_opa(p->slider,LV_PART_KNOB)==LV_OPA_TRANSP);
  size_t matching=0;for(const auto& s:*p->spools)if(s.material==p->material)matching++;
  CHECK(p->visible.size()==matching);for(int index:p->visible)CHECK((*p->spools)[index].material==p->material);
 }
 touch(160,234);CHECK(p->axis==1);for(int index:p->visible)CHECK((*p->spools)[index].material=="PLA"&&(*p->spools)[index].saturation<.15f);
 // Exiting the material menu preserves the current filter; ALL clears it.
 materialChoice=-1;inventoryPickMaterial(p);CHECK(p->material=="PLA"&&p->axis==1);
 materialChoice=0;inventoryPickMaterial(p);CHECK(p->material.empty()&&p->axis==0&&p->visible.size()==p->spools->size());
 p->material="absent";inventoryPickerFilter(p);pump();
 CHECK(p->visible.empty()&&!lv_obj_has_flag(p->empty,LV_OBJ_FLAG_HIDDEN));
 (*p->spools)[0].material="unique";p->material="unique";p->axis=0;inventoryPickerFilter(p);pump();
 CHECK(p->visible.size()==1&&lv_obj_get_scroll_x(p->row)==0);
 p->material="";inventoryPickerFilter(p);pump();CHECK(p->visible.size()==p->spools->size());
}

int main(){lv_init();static lv_color_t pixels[480*40];static lv_disp_draw_buf_t buf;lv_disp_draw_buf_init(&buf,pixels,nullptr,480*40);static lv_disp_drv_t disp;lv_disp_drv_init(&disp);disp.hor_res=480;disp.ver_res=320;disp.draw_buf=&buf;disp.flush_cb=[](lv_disp_drv_t* d,const lv_area_t*,lv_color_t*){if(transitionHome==lv_scr_act())homeFlushes++;lv_disp_flush_ready(d);};lv_disp_drv_register(&disp);static lv_indev_drv_t indev;lv_indev_drv_init(&indev);indev.type=LV_INDEV_TYPE_POINTER;indev.read_cb=input;lv_indev_drv_register(&indev);
 // A completed prepare must not paint home before the next writing screen.
 lv_timer_set_period(_lv_disp_get_refr_timer(nullptr),1);pump();transitionHome=lv_scr_act();
 InventoryRequest request;CHECK(inventoryWait(request,I18N_INV_EXIT,false));CHECK(homeFlushes==0);
 lv_obj_t* writing=lv_obj_create(nullptr);lv_scr_load(writing);pump();CHECK(homeFlushes==0);
 lv_scr_load(transitionHome);pump();CHECK(homeFlushes>0);lv_obj_del(writing);transitionHome=nullptr;
 std::vector<InventorySpool> spools;for(int i=0;i<1000;i++){InventorySpool s;s.id=std::to_string(i);s.label="Fixture";s.material=i%2?"PLA":"PETG";s.rgb=i<5?(0x333333*i):lv_color_to32(lv_color_hsv_to_rgb(((i-5)*14)%360,100,100))&0xFFFFFF;inventoryColor(s);spools.push_back(s);}std::sort(spools.begin(),spools.end(),inventoryColorLess);transitionHome=lv_scr_act();homeFlushes=0;inventoryPickSpool(spools);CHECK(homeFlushes==0);transitionHome=nullptr;
 // Confirm returns the selected spool directly; Exit still returns no selection.
 pickerMode=1;CHECK(inventoryPickSpool(spools)==0);CHECK(confirmationDialogs==0);
 gBlankFlowRemoved=false;pickerMode=2;CHECK(inventoryPickSpool(spools)==-1);CHECK(confirmationDialogs==0);
 pickerMode=0;gBlankFlowRemoved=false;
 InventoryRequest chooseBox;CHECK(selectSpoolContainer(chooseBox,true));CHECK(chooseBox.containerId=="box0"&&chooseBox.containerWeight==200&&containerSaves==1);CHECK(!gBlankFlowActive&&!gBlankLoadLatched);
 containerMode=2;InventoryRequest exitBox;CHECK(!selectSpoolContainer(exitBox,true));CHECK(containerSaves==1&&exitBox.containerId.empty()&&!gBlankFlowActive&&!gBlankLoadLatched);
 containerMode=3;InventoryRequest removedBox;CHECK(!selectSpoolContainer(removedBox,true));CHECK(containerSaves==1&&gBlankFlowRemoved&&!gBlankFlowActive);
 gBlankFlowRemoved=false;gBlankLoadLatched=gBlankLoadWasPresent=false;containerKnown=true;
 InventoryRequest knownBox;int screens=containerScreens;CHECK(selectSpoolContainer(knownBox,true));CHECK(containerScreens==screens&&containerSaves==1&&knownBox.containerId=="known");
 containerKnown=false;containerFailure=true;InventoryRequest failedBox;CHECK(!selectSpoolContainer(failedBox,true));CHECK(containerNotices==1&&containerSaves==1&&!gBlankFlowActive&&!gBlankLoadLatched);
 containerFailure=false;containerMode=0;gBlankFlowActive=gBlankLoadLatched=true;InventoryRequest deferredBox;CHECK(selectSpoolContainer(deferredBox,false));CHECK(deferredBox.containerId=="box0"&&containerSaves==1&&gBlankFlowActive&&gBlankLoadLatched);
 printf("PASS: %d native LVGL picker checks (1000 spools)\n",checks);
}
'''
src=OUT/'picker.cpp';src.write_text(shim+'enum {'+','.join(keys)+'};\n'+funcs+tail,encoding='utf-8')
exe=OUT/('picker.exe' if os.name=='nt' else 'picker');subprocess.run([CXX,'-std=c++11',*(['-static'] if os.name=='nt' else []),*flags,str(src),*[str(x) for x in objs],'-o',str(exe)],env=env,check=True)
result=subprocess.run([str(exe)],env=env)
raise SystemExit(result.returncode)
