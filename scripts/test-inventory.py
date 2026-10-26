#!/usr/bin/env python3
"""Native checks of the firmware's inventory codec, migration, writer and lift latch.
Requires g++ and ArduinoJson already installed by a PlatformIO project build.
No device, network, account or tag writes. Run: python scripts/test-inventory.py
"""
from pathlib import Path
import os, shutil, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'TigerTagSplashESP32/TigerTagSplashESP32.ino'
def extract(signature):
    result=[]; depth=0; started=False
    with SOURCE.open(encoding='utf-8') as f:
        for line in f:
            if not result and (not line.lstrip().startswith(signature) or line.rstrip().endswith(";")): continue
            result.append(line); depth += line.count('{')-line.count('}')
            if '{' in line: started=True
            if started and depth==0: return ''.join(result)
    raise RuntimeError('Missing firmware function: '+signature)
shim=r'''
#include <ArduinoJson.h>
#include "bambu_catalog.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <map>
#include <ctime>
using std::isfinite;
class String : public std::string {
public:
 String():std::string(){} String(const char* s):std::string(s?s:""){}
 String(const std::string& s):std::string(s){}
 String(uint64_t n):std::string(std::to_string(n)){}
 String(unsigned n):std::string(std::to_string(n)){}
 String(int n):std::string(std::to_string(n)){}
 String(double n,int){char b[40];snprintf(b,sizeof(b),"%.0f",n);assign(b);}
 int lastIndexOf(char c)const{auto p=rfind(c);return p==npos?-1:(int)p;}
 bool startsWith(const char* s)const{return rfind(s,0)==0;}
 void toUpperCase(){for(char& c:*this)if(c>='a'&&c<='z')c-='a'-'A';}
 bool isEmpty()const{return empty();}
 String substring(size_t a,size_t b)const{return substr(a,b-a);}
 String substring(size_t a)const{return substr(a);}
 void trim(){auto a=find_first_not_of(" \t\r\n"),b=find_last_not_of(" \t\r\n");assign(a==npos?"":substr(a,b-a+1));}
 bool equalsIgnoreCase(const String& b)const{String a=*this,c=b;a.toUpperCase();c.toUpperCase();return a==c;}
};
ARDUINOJSON_BEGIN_PUBLIC_NAMESPACE
 template<> struct Converter<String>{
  static void toJson(const String& v,JsonVariant d){d.set(std::string(v));}
  static String fromJson(JsonVariantConst v){return String(v.isNull()?"null":v.as<const char*>());}
  static bool checkJson(JsonVariantConst v){return v.is<const char*>();}
 };
ARDUINOJSON_END_PUBLIC_NAMESPACE
using InventoryJson=DynamicJsonDocument;
struct InventorySpool{String id,version,label,material;bool containerKnown=false;uint32_t rgb=0;float hue=0,saturation=0,value=0;};
struct SpoolContainer{String id,label,type;uint16_t brand=0;float weight=0;};
struct BambuTag{String uid,variant,materialCode,material,detail;uint32_t rgba=0;uint16_t grams=0;float diameter=0;};
struct InventoryRequest{BambuTag bambu;bool found=false;uint32_t productId=0;float rawWeight=0;std::vector<InventorySpool> spools;std::vector<SpoolContainer> containers;String containerId;float containerWeight=0;enum Operation{LIST,PREPARE,COMMIT,PREPARE_RELEASE,RELEASE,CONTAINERS,SET_CONTAINER,BAMBU_LOOKUP,BAMBU_CREATE,BAMBU_UPGRADE};Operation op=LIST;int error=0;bool cancel=false,ok=false;String source,version,owner,conflictUid,uids[2],releaseIds[2],previousLabel;String releaseVersions[2];int8_t releaseChoice=-1;uint8_t releaseCount=0;uint32_t stamp=123456;uint8_t payload[144]={};};
std::map<uint16_t,String> gBrandDb,gMaterialDb;
String mapColorName(uint8_t,uint8_t,uint8_t){return "White";}
BambuTag gBambuTags[2];uint32_t gBambuSeenMs[2]={},gBambuPairSinceMs=0;bool gBambuPending=false;String gBambuSingleChecked,gBambuReadyUid[2],gBambuOwner;
String firebaseUid="owner";
const char* INVENTORY_ROOT="https://example.test/documents";
#define MALLOC_CAP_INTERNAL 1
size_t heap_caps_get_free_size(int){return 128000;}
size_t heap_caps_get_largest_free_block(int){return 128000;}
std::vector<std::string> pages,requests;std::vector<int> pageCodes;int pageCode=200;
std::vector<bool> authenticatedGets;
int activeTlsClients=0;bool requireSingleTls=false;
int inventoryGet(const String& url,InventoryJson& doc,bool authenticated=true){doc.clear();requests.push_back(url);authenticatedGets.push_back(authenticated);if(requireSingleTls&&activeTlsClients)return -1;if(requests.size()>pages.size())return 400;int code=pageCodes.size()>=requests.size()?pageCodes[requests.size()-1]:pageCode;if(code!=200)return code;return deserializeJson(doc,pages[requests.size()-1],DeserializationOption::NestingLimit(96))?-2:200;}
uint32_t esp_random(){static uint32_t n=1000000000;return n++;}
uint32_t nowMs=1;uint32_t millis(){return nowMs;}
void netLog(const String&){} void lv_timer_handler(){} void blankFlowTick(){} void delay(unsigned long){}
bool gBlankFlowActive=false,gBlankFlowRemoved=false,gZeroRequired=false;
const char* t(int);bool lvglAskYesNo(const char*,const char*,int,int);
int repositionAccepts=0,repositionMode=0;std::vector<String> repositionDirections;
struct PN532Reader {
 uint16_t atqa=0;uint8_t sak=0;bool classicAuth=false;int authCalls=0;uint8_t classicMem[6][16]={};
 bool authenticateBambuSector(uint8_t){authCalls++;return classicAuth;}
 struct {uint8_t size=7;uint8_t uidByte[7]={4};}uid;
 uint8_t mem[256];String identity;bool present=true,readable=true,fieldOn=true,fieldOK=true;int fieldCalls=0;int selections=0,swapAt=0,missAt=-1,noUidAttempts=0,readFailures=0;
 bool configureRfField(bool on){fieldCalls++;if(!fieldOK)return false;fieldOn=on;return true;}
 int failPage=-1,failures=-1,writeCalls=0,removeAt=-1,failReadOnPage=-1,failReadCount=1;bool changeMarkerOnFailure=false,lostAck=false,badBody=false,badFinal=false,protectedWrite=false;
 int pageCount=0,failReadPage=-1;uint8_t pages[128]={};
 PN532Reader(){memset(mem,0xA5,sizeof(mem));const uint8_t hdr[]={0xE1,0x11,0x3E,0,3,4,0xD8,0,0,0,0xFE,0,0,0,0,0};memcpy(mem+12,hdr,16);}
 bool readPages16(uint8_t page,uint8_t* out){if(readFailures>0){readFailures--;return false;}if(!readable||page==failReadPage)return false;memcpy(out,classicAuth?classicMem[page]:mem+page*4,16);if((badBody&&pageCount>0)||(badFinal&&mem[16]!=3))out[5]^=1;return true;}
 bool writePage(uint8_t page,const uint8_t* data){writeCalls++;if(page<4||page>0x27){protectedWrite=true;return false;}bool fail=page==failPage&&(failures<0||failures-->0);if(fail&&changeMarkerOnFailure)mem[16]=0x77;if(fail&&!lostAck)return false;pages[pageCount++]=page;memcpy(mem+page*4,data,4);if(page==failReadOnPage){readFailures=failReadCount;failReadOnPage=-1;}if(writeCalls==removeAt)gBlankFlowRemoved=true;return !fail;}
};
std::map<String,int> gMetaCache,nvsCache;
struct Preferences{bool begin(const char*,bool){return true;}bool isKey(const char* k){return nvsCache.count(String(k));}void remove(const char* k){nvsCache.erase(String(k));}void end(){}};
#define RFID_TRANSPORT_HSU 1
uint8_t gReaderTagState[2]={};String gReaderTagUid[2];
String gTagReadBeepUid[2];uint32_t gTagBeepEmptySinceMs=0;int readBeeps=0;
float readWeight();void playSoundTheme(bool single){if(single)readBeeps++;}
bool gRfid1Present=true,gRfid2Present=true;
PN532Reader rfid1,rfid2;String gBlankTagUid[2],lastUID,lastUID2,lastUIDHex,lastUID2Hex,lastUIDLeft,lastUIDRight,lastUIDTwin,gLastManufacturer,gLastMaterial,gLastColor;uint32_t gBlankTagSeenMs[2]={},gRfidReadOkCount=0,gRfidReadFailCount=0;
#define RFID_DEBUG_PRINTF(...)
String readRFIDFromReaderTestStyle(PN532Reader&r,String&out,const char*,bool*){r.selections++;out=(!r.present||r.selections<=r.noUidAttempts||r.selections==r.missAt)?String(""):(r.selections==r.swapAt?String("OTHER"):r.identity);return out;}
void finishRfidSession(PN532Reader&){}
static void clearRemovedSpool();
bool gBlankLoadLatched=false,gBlankLoadWasPresent=false,gBlankLoadWritten=false,gHx711Online=true,gBlankTagNoticePending=false,gAssignmentRecoveryPending=false;
uint32_t gBlankEmptySinceMs=0,gBlankPairSinceMs=0,gHx711NotReadySinceMs=0;
float gBlankLoadSampleWeight=NAN;uint32_t gBlankLoadSampleMs=0;
float currentWeight=0;const float SCAN_START_WEIGHT_G=20,MIN_WEIGHT_TO_SEND_G=5;
std::map<String,std::string> savedJson;
std::string releaseRequest;int postCode=200,postCalls=0;
struct File{std::string data;size_t at=0;File(const std::string& s=""):data(s){}operator bool()const{return !data.empty();}int read(){return at<data.size()?(unsigned char)data[at++]:-1;}size_t readBytes(char* b,size_t n){size_t got=0;while(got<n&&at<data.size())b[got++]=data[at++];return got;}size_t size(){return data.size();}void close(){}};
const char* ASSIGN_COMMIT="commit";const char* ASSIGN_META="pending";const char* ASSIGN_RELEASE="release";bool pendingFileExists=false;struct{bool exists(const char* p){return (strcmp(p,ASSIGN_META)!=0&&strcmp(p,"/tag-assignment.json")!=0)||pendingFileExists;}bool remove(const char* p){savedJson.erase(String(p));return true;}File open(const char* p,const char*){auto i=savedJson.find(String(p));return File(i==savedJson.end()?releaseRequest:i->second);}}LittleFS;
int inventoryPostCommit(const char*){postCalls++;return postCode;}
bool inventorySaveJson(const char* path,JsonVariantConst doc){std::string text;serializeJson(doc,text);savedJson[path]=text;if(!strcmp(path,ASSIGN_META))pendingFileExists=true;return true;}
void resetReaders(){repositionAccepts=repositionMode=0;repositionDirections.clear();rfid1=PN532Reader();rfid2=PN532Reader();rfid1.identity="04112233445566";rfid2.identity="04778899AABBCC";}
void number(JsonObject f,const char* key,double value){f.remove(key);f[key]["doubleValue"]=value;}
uint32_t get(const uint8_t* p,int at,int n){uint32_t v=0;while(n--)v=(v<<8)|p[at++];return v;}
'''
performance_shim=r'''
class Stream {
public:
 virtual ~Stream(){} virtual int available()=0; virtual int read()=0; virtual int peek()=0;
 virtual void flush()=0; virtual size_t write(uint8_t)=0;
 virtual size_t write(const uint8_t*,size_t)=0;
};
#define MALLOC_CAP_SPIRAM 2
#define MALLOC_CAP_8BIT 4
void* heap_caps_realloc(void* p,size_t n,int){return realloc(p,n);}
void heap_caps_free(void* p){free(p);}
struct WiFiClientSecure{WiFiClientSecure(){activeTlsClients++;}~WiFiClientSecure(){activeTlsClients--;}void setInsecure(){}};
struct HttpReply{int code;std::string body;int failure=0;HttpReply(int c,std::string b,int f=0):code(c),body(b),failure(f){}};
std::vector<HttpReply> httpReplies;int httpCalls=0,httpEnds=0,refreshes=0;
std::vector<int> postReplies;std::vector<String> postedBodies;int authHeaders=0;
bool refreshOK=true;uint32_t firebaseTokenMs=0;String firebaseIdToken="fixture";
InventoryRequest* gInventoryRequest=nullptr;
bool ensureFirebaseToken(){refreshes++;return refreshOK;}
struct HTTPClient {
 int index=0;void setTimeout(int){}void useHTTP10(bool){}bool begin(WiFiClientSecure&,const String&){return true;}
 void addHeader(const char* name,const String&){if(!strcmp(name,"Authorization"))authHeaders++;}
 int POST(const String& body){postedBodies.push_back(body);return postedBodies.size()<=postReplies.size()?postReplies[postedBodies.size()-1]:403;}
 int sendRequest(const char*,File* file,size_t){return POST(String(file->data));}String getString(){return "{}";}
 int GET(){index=httpCalls++;return index<(int)httpReplies.size()?httpReplies[index].code:403;}
 int writeToStream(Stream* stream){auto& r=httpReplies[index];if(r.failure)return r.failure;size_t sent=0;
  while(sent<r.body.size()){size_t n=std::min((size_t)17,r.body.size()-sent);if(stream->write((const uint8_t*)r.body.data()+sent,n)!=n)return -10;sent+=n;}return sent;}
 void end(){httpEnds++;}
};
using std::isnan;using std::isinf;
struct {void println(const char*){}} Serial;
struct {float raw=0;bool ready=true;bool is_ready(){return ready;}bool wait_ready_timeout(int,int){return ready;}float get_units(int){return raw;}}scale;
const int MEDIAN_WINDOW_LARGE=5;
const float EMA_ALPHA_FINE=.04f,EMA_ALPHA_FAST=.35f,HYSTERESIS_THRESHOLD=.5f,DEAD_ZONE_G=1;
const uint32_t STABLE_DISPLAY_MS=1500;
float gEmaWeight=0,gMedianBuf[5]={},gLastDisplayedWeight=0,gWeightStepCandidate=NAN;
bool gEmaInit=false,gIsStable=false;int gMedianIdx=0,gMedianCount=0;
uint32_t gWeightStepMs=0,gStableStartMs=0;

'''

tests=r'''
void tick(){if(gHx711Online){gBlankLoadSampleWeight=currentWeight;gBlankLoadSampleMs=nowMs;}blankLoadTick();}
int main(){int checks=0;
#define CHECK(x) do{if(!(x)){printf("FAIL line %d: %s\n",__LINE__,#x);return 1;}checks++;}while(0)
 DynamicJsonDocument doc(16384);auto f=doc.to<JsonObject>();
 const char* keys[]={"id_product","id_material","id_aspect1","id_type","data1","id_brand","color_r","color_g","color_b","color_a","measure","id_unit","data2","data3","data4","data5","data6","data7","weight_available"};
 double vals[]={2358133083.,46591,104,142,56,47930,80,7,120,255,1000,21,210,230,50,8,45,60,1000};
 for(int i=0;i<19;i++)number(f,keys[i],vals[i]);f["message"]["stringValue"]="eSun PLA+ PURPLE";
 uint8_t data[144];CHECK(inventoryEncode(f,123456,data));
 const char* hex="BC0FCB978C8E415BB5FF68008E38BB3A500778FF0003E81500D200E632082D3C0001E2400000000000000000000000006553756E20504C412B20505552504C450000000000000000000000000003E800";
 CHECK(strlen(hex)==160);for(int i=0;i<80;i++){unsigned n;sscanf(hex+2*i,"%2x",&n);CHECK(data[i]==n);}
 for(int i=80;i<144;i++)CHECK(data[i]==0);
 uint8_t original[144];memcpy(original,data,144);
 number(f,"id_unit",35);number(f,"measure",1);number(f,"weight_available",1303);CHECK(inventoryEncode(f,123456,data));CHECK(get(data,76,3)==1&&get(data,20,3)==1);
 f.remove("weight_available");number(f,"measure_gr",2000);CHECK(inventoryEncode(f,123456,data));CHECK(get(data,76,3)==2);
 f.remove("measure_gr");CHECK(inventoryEncode(f,123456,data));CHECK(get(data,76,3)==1);
 number(f,"id_unit",10);number(f,"measure",1000000);number(f,"weight_available",1303);CHECK(inventoryEncode(f,1,data));CHECK(get(data,76,3)==1303000);
 number(f,"id_unit",21);number(f,"measure",1000);number(f,"weight_available",0);CHECK(inventoryEncode(f,1,data));CHECK(get(data,76,3)==0);
 number(f,"weight_available",16777216);CHECK(!inventoryEncode(f,1,data));number(f,"weight_available",-1);CHECK(!inventoryEncode(f,1,data));number(f,"weight_available",1000);
 number(f,"id_unit",0);CHECK(!inventoryEncode(f,1,data));number(f,"id_unit",21);
 number(f,"data2",65536);CHECK(!inventoryEncode(f,1,data));number(f,"data2",210);
 number(f,"color_r",-1);CHECK(!inventoryEncode(f,1,data));number(f,"color_r",80);
 number(f,"data1",56.5);CHECK(!inventoryEncode(f,1,data));number(f,"data1",56);
 number(f,"TD",1.5);number(f,"color_r2",12);number(f,"color_g3",77);CHECK(inventoryEncode(f,1,data));CHECK(get(data,44,2)==15&&data[36]==12&&data[41]==77);
 number(f,"id_product",0);CHECK(inventoryEncode(f,1,data));CHECK(get(data,0,4)==1542820452UL&&get(data,4,4)==0xFFFFFFFFUL);
 f.remove("id_product");CHECK(inventoryEncode(f,1,data));CHECK(get(data,0,4)==1542820452UL);
 f["message"]["stringValue"]=std::string(27,'x')+"\xE7\xBA\xA2";CHECK(inventoryEncode(f,1,data));CHECK(data[74]=='x'&&data[75]==0xE7);
 // Golden bytes from the pinned official JS/Python serializers and protocol guide.
 InventoryJson encodingFixtures(65536),encodingFields(4096);
 CHECK(!deserializeJson(encodingFixtures,TAG_ENCODING_FIXTURE));
 for(JsonObjectConst sample:encodingFixtures["cases"].as<JsonArrayConst>()){
  encodingFields.clear();auto fields=encodingFields.to<JsonObject>();
  for(JsonPairConst item:sample["fields"].as<JsonObjectConst>()){
   if(item.value().is<const char*>())fields[item.key()]["stringValue"]=item.value();
   else fields[item.key()]["doubleValue"]=item.value();
  }
  CHECK(inventoryEncode(fields,sample["stamp"],data));data[39]=sample["tagInfo"];
  String expected=sample["expectedHex"].as<String>();CHECK(expected.length()==160);
  for(int i=0;i<80;i++){unsigned value;sscanf(expected.c_str()+2*i,"%2x",&value);CHECK(data[i]==value);}
 }
 CHECK(inventoryChipless("TigerData_123",f));CHECK(inventoryChipless("CLOUD_123",f));CHECK(!inventoryChipless("04112233445566",f));
 CHECK(inventoryChipless("TIGERDATA_9000000031",f));CHECK(inventoryChipless("tigerdata_123",f));CHECK(inventoryChipless("cloud_123",f));
 f["deleted"]["booleanValue"]=true;CHECK(!inventoryChipless("TigerData_1",f));f.remove("deleted");number(f,"id_type",1);CHECK(!inventoryChipless("CLOUD_1",f));number(f,"id_type",142);
 std::vector<InventorySpool> colors;uint32_t rgb[]={0x808080,0xFF00FF,0x0000FF,0x00FF00,0xFFFF00,0x00FFFF,0xFF0000,0};
 for(int i=0;i<8;i++){InventorySpool s;s.rgb=rgb[i];s.id=String(i);inventoryColor(s);colors.push_back(s);}std::sort(colors.begin(),colors.end(),inventoryColorLess);
 uint32_t sorted[]={0x808080,0,0xFF0000,0xFFFF00,0x00FF00,0x00FFFF,0x0000FF,0xFF00FF};for(int i=0;i<8;i++)CHECK(colors[i].rgb==sorted[i]);
 // Material and axis filters combine; the stored ID/index remains unchanged.
 colors[0].material="PLA";colors[2].material="PETG";
 CHECK(inventoryMatches(colors[0],"",0));CHECK(inventoryMatches(colors[2],"",0));
 CHECK(inventoryMatches(colors[0],"pla",1));CHECK(!inventoryMatches(colors[0],"PLA",2));
 CHECK(inventoryMatches(colors[2],"petg",2));CHECK(!inventoryMatches(colors[2],"PLA",2));
 CHECK(!inventoryMatches(colors[2],"",1));
 InventorySpool pale;pale.rgb=0xFFEEEE;inventoryColor(pale);CHECK(pale.saturation>.9f); // HSL, not HSV
 // Actual writer: UID preflight, marker-last, full verification and pair failures.
 resetReaders();String uids[]={rfid1.identity,rfid2.identity};CHECK(writeInventoryTags(original,uids)==2);
 original[39]=0x12;CHECK(memcmp(rfid1.mem+16,original,80)==0);original[39]=0x22;CHECK(memcmp(rfid2.mem+16,original,80)==0);
 for(auto r:{&rfid1,&rfid2}){CHECK(r->pageCount==20);CHECK(r->pages[0]==5&&r->pages[19]==4);CHECK(!r->protectedWrite);CHECK(r->mem[0]==0xA5&&r->mem[11]==0xA5&&r->mem[12]==0xE1&&r->mem[160]==0xA5);}
 for(auto r:{&rfid1,&rfid2}){for(int i=96;i<160;i++)CHECK(r->mem[i]==0xA5);for(int i=0;i<r->pageCount;i++)CHECK(r->pages[i]<=0x17);}
 // Normal writes must never touch signature pages, even if they reject writes.
 resetReaders();rfid1.failPage=rfid2.failPage=0x18;CHECK(writeInventoryTags(original,uids)==2);
 for(auto r:{&rfid1,&rfid2})for(int i=96;i<160;i++)CHECK(r->mem[i]==0xA5);
 resetReaders();String duplicate[]={uids[0],uids[0]};CHECK(writeInventoryTags(original,duplicate)==0&&rfid1.pageCount==0);
 resetReaders();String missing[]={uids[0],""};CHECK(writeInventoryTags(original,missing)==0&&rfid1.pageCount==0);
 resetReaders();rfid2.present=false;CHECK(writeInventoryTags(original,uids)==0&&rfid1.pageCount==0);
 resetReaders();rfid2.mem[16]=0xBC;CHECK(writeInventoryTags(original,uids)==0&&rfid1.pageCount==0);
 resetReaders();rfid1.swapAt=2;CHECK(writeInventoryTags(original,uids)==0&&rfid1.pageCount==0);
 resetReaders();rfid1.failPage=8;CHECK(writeInventoryTags(original,uids)==0&&rfid1.mem[16]==3&&rfid2.pageCount==0);
 resetReaders();rfid1.badBody=true;CHECK(writeInventoryTags(original,uids)==0&&rfid1.mem[16]==3&&rfid2.pageCount==0);
 resetReaders();rfid1.swapAt=3;CHECK(writeInventoryTags(original,uids)==0&&rfid1.mem[16]==3&&rfid2.pageCount==0);
 resetReaders();rfid1.badFinal=true;CHECK(writeInventoryTags(original,uids)==0&&rfid1.mem[16]==0xBC&&rfid2.pageCount==0);
 resetReaders();rfid2.failPage=8;CHECK(writeInventoryTags(original,uids)==1&&rfid1.mem[16]==0xBC&&rfid2.mem[16]==3);
 // Transient page failures resume partial contents only on the original UID.
 resetReaders();rfid1.failPage=8;rfid1.failures=1;CHECK(writeInventoryTags(original,uids)==2);CHECK(rfid1.pageCount==23&&rfid2.pageCount==20);
 resetReaders();rfid2.failPage=8;rfid2.failures=2;CHECK(writeInventoryTags(original,uids)==2);CHECK(rfid1.pageCount==20&&rfid2.pageCount==26);
 original[39]=0x12;CHECK(memcmp(rfid1.mem+16,original,80)==0);original[39]=0x22;CHECK(memcmp(rfid2.mem+16,original,80)==0);
 // A marker may have been programmed even though its ACK was lost.
 resetReaders();rfid1.failPage=4;rfid1.failures=1;rfid1.lostAck=true;CHECK(writeInventoryTags(original,uids)==2);CHECK(rfid1.pageCount==40&&rfid2.pageCount==20);
 resetReaders();rfid1.failPage=8;CHECK(writeInventoryTags(original,uids)==0);CHECK(rfid1.writeCalls==12&&rfid2.writeCalls==0);
 resetReaders();rfid1.noUidAttempts=2;CHECK(writeInventoryTags(original,uids)==2);
 resetReaders();rfid2.readFailures=1;CHECK(writeInventoryTags(original,uids)==2);
 resetReaders();rfid1.noUidAttempts=4;CHECK(writeInventoryTags(original,uids)==2);
 resetReaders();rfid2.readFailures=4;CHECK(writeInventoryTags(original,uids)==2);
 resetReaders();rfid1.failPage=8;rfid1.failures=1;rfid1.swapAt=3;CHECK(writeInventoryTags(original,uids)==0);CHECK(rfid1.pageCount==3&&rfid2.pageCount==0);
 resetReaders();rfid1.failPage=8;rfid1.failures=1;rfid1.missAt=3;CHECK(writeInventoryTags(original,uids)==2);
 resetReaders();rfid1.failReadOnPage=0x17;CHECK(writeInventoryTags(original,uids)==2);CHECK(rfid1.pageCount==20&&rfid2.pageCount==20);
 resetReaders();rfid1.failPage=8;rfid1.failures=1;rfid1.changeMarkerOnFailure=true;CHECK(writeInventoryTags(original,uids)==0);CHECK(rfid1.writeCalls==4&&rfid2.writeCalls==0);
 resetReaders();rfid1.removeAt=2;CHECK(writeInventoryTags(original,uids)==0);CHECK(rfid1.writeCalls==2&&rfid2.writeCalls==0);gBlankFlowRemoved=false;
 // Verification read retries do not rewrite a successfully programmed body or marker.
 for(int failurePage:{0x17,0x04}) for(int count:{1,2}) {
  resetReaders();rfid1.failReadOnPage=failurePage;rfid1.failReadCount=count;
  CHECK(writeInventoryTags(original,uids)==2);CHECK(rfid1.pageCount==20&&rfid2.pageCount==20);
 }
 // Exhaustion is bounded, then the existing whole-tag retry can recover.
 resetReaders();rfid1.failReadOnPage=0x17;rfid1.failReadCount=3;
 CHECK(writeInventoryTags(original,uids)==2);CHECK(rfid1.pageCount==39);
 // Re-selection must not continue verification or write the marker on a different UID.
 resetReaders();rfid1.failReadOnPage=0x17;rfid1.swapAt=3;
 CHECK(writeInventoryTags(original,uids)==0);CHECK(rfid1.pageCount==19&&rfid1.mem[16]==3&&rfid2.pageCount==0);
 resetReaders();rfid1.failReadOnPage=4;rfid1.swapAt=4;
 CHECK(writeInventoryTags(original,uids)==0);CHECK(rfid1.pageCount==20&&rfid2.pageCount==0);
 // A missed recovery selection may be retried, retaining the same UID guard.
 resetReaders();rfid1.failReadOnPage=0x17;rfid1.missAt=3;
 CHECK(writeInventoryTags(original,uids)==2);CHECK(rfid1.pageCount==20);
 // Erase shares verification recovery and must still verify every byte on both tags.
 uint8_t erasedPayload[144]={};
 resetReaders();rfid1.failReadOnPage=0x27;rfid2.failReadOnPage=4;
 CHECK(writeInventoryTags(erasedPayload,uids,true)==2);
 CHECK(rfid1.pageCount==36&&rfid2.pageCount==36);
 CHECK(!memcmp(rfid1.mem+16,erasedPayload,144)&&!memcmp(rfid2.mem+16,erasedPayload,144));
 // Guided retries retain verified work and point toward the failing physical reader.
 resetReaders();rfid1.noUidAttempts=6;repositionAccepts=1;
 CHECK(writeInventoryTags(original,uids)==2);CHECK(repositionDirections.size()==1&&repositionDirections[0]=="move-right");
 resetReaders();rfid2.failPage=8;repositionAccepts=repositionMode=1;
 CHECK(writeInventoryTags(original,uids)==2);CHECK(repositionDirections.size()==1&&repositionDirections[0]=="move-left");
 CHECK(rfid1.pageCount==20&&rfid2.pageCount==29);
 resetReaders();rfid1.failPage=rfid2.failPage=8;repositionAccepts=2;repositionMode=1;
 CHECK(writeInventoryTags(erasedPayload,uids,true)==2);
 CHECK(repositionDirections.size()==2&&repositionDirections[0]=="move-right"&&repositionDirections[1]=="move-left");
 CHECK(rfid1.pageCount==45&&rfid2.pageCount==45);
 CHECK(!memcmp(rfid1.mem+16,erasedPayload,144)&&!memcmp(rfid2.mem+16,erasedPayload,144));
 // Cancel retains the completed tag; changed identities and removal never resume writes.
 resetReaders();rfid2.failPage=8;
 CHECK(writeInventoryTags(original,uids)==1);CHECK(repositionDirections.size()==1&&rfid1.pageCount==20&&rfid2.writeCalls==12);
 resetReaders();rfid1.failPage=8;repositionAccepts=1;repositionMode=2;
 CHECK(writeInventoryTags(original,uids)==0);CHECK(rfid1.writeCalls==12&&rfid2.writeCalls==0);
 resetReaders();rfid1.failPage=8;repositionAccepts=1;repositionMode=3;
 CHECK(writeInventoryTags(original,uids)==0);CHECK(rfid1.writeCalls==12&&rfid2.writeCalls==0);gBlankFlowRemoved=false;
 resetReaders();rfid1.swapAt=2;
 CHECK(writeInventoryTags(original,uids)==0&&repositionDirections.empty());
 // Recovery follows UID identity even if the spool is turned around.
 InventoryRequest recovery;recovery.uids[0]=uids[0];recovery.uids[1]=uids[1];memcpy(recovery.payload,original,144);
 resetReaders();CHECK(writeInventoryTags(original,uids)==2);CHECK(inventoryVerifyPair(recovery,false));
 std::swap(rfid1,rfid2);CHECK(inventoryVerifyPair(recovery,false));rfid1.mem[100]^=1;CHECK(inventoryVerifyPair(recovery,false));rfid1.mem[95]^=1;CHECK(!inventoryVerifyPair(recovery,false));
 resetReaders();std::swap(rfid1,rfid2);CHECK(inventoryVerifyPair(recovery,true));rfid1=rfid2;CHECK(!inventoryVerifyPair(recovery,true));
 // Studio/SDK erasure is all zeros; retained signatures are outside the blank record.
 for(int capacity:{0x12,0x3E,0x6D}){
  resetReaders();rfid1.mem[14]=capacity;memset(rfid1.mem+16,0,80);bool readOK=false;
  CHECK(isBlankNtag(rfid1,&readOK)&&readOK);
  for(int at=16;at<96;at++){rfid1.mem[at]=1;CHECK(!isBlankNtag(rfid1));rfid1.mem[at]=0;}
 }
 resetReaders();for(auto r:{&rfid1,&rfid2})memset(r->mem+16,0,80);
 CHECK(inventoryVerifyPair(recovery,true));CHECK(writeInventoryTags(original,uids)==2);CHECK(inventoryVerifyPair(recovery,false));
 for(auto r:{&rfid1,&rfid2})for(int i=96;i<160;i++)CHECK(r->mem[i]==0xA5);
 // Verification retries only missing targets/failed reads, never mismatches.
 resetReaders();memset(rfid1.mem+16,0,80);rfid1.failReadPage=0x14;bool readBlank=true;
 CHECK(!isBlankNtag(rfid1,&readBlank)&&!readBlank);
 CHECK(writeInventoryTags(original,uids)==0&&rfid1.writeCalls==0&&rfid2.writeCalls==0);
 resetReaders();rfid1.noUidAttempts=2;CHECK(inventoryVerifyPair(recovery,true));CHECK(rfid1.selections==3);
 resetReaders();rfid2.readFailures=1;CHECK(inventoryVerifyPair(recovery,true));CHECK(rfid2.selections==2);
 resetReaders();rfid1.present=false;CHECK(!inventoryVerifyPair(recovery,true));CHECK(rfid1.selections==3);
 resetReaders();rfid1.identity="OTHER";CHECK(!inventoryVerifyPair(recovery,true));CHECK(rfid1.selections==1);
 // RF configuration sends a real field command and consumes its response.
 FieldProbe field;CHECK(field.configureRfField(false));CHECK(field._pn532.sent[0]==0x32&&field._pn532.sent[1]==1&&field._pn532.sent[2]==0&&field.reads==1);
 CHECK(field.configureRfField(true)&&field._pn532.sent[2]==1);field._pn532.ack=false;CHECK(!field.configureRfField(false)&&field.reads==2);
 field._pn532.ack=true;field.command=0x4B;CHECK(!field.configureRfField(false));field.command=0x33;field.length=3;CHECK(!field.configureRfField(false));
 resetReaders();CHECK(prepareRfidRead(rfid1));CHECK(rfid1.fieldOn&&!rfid2.fieldOn);CHECK(prepareRfidRead(rfid2));CHECK(!rfid1.fieldOn&&rfid2.fieldOn);
 resetReaders();rfid2.fieldOK=false;CHECK(!prepareRfidRead(rfid1)&&rfid1.fieldCalls==0);gRfid2Present=false;CHECK(prepareRfidRead(rfid1));gRfid2Present=true;
 // A brief dip, antenna loss or sensor outage cannot re-arm a dismissed load.
 pendingFileExists=true;gBlankLoadLatched=true;gBlankLoadWasPresent=true;currentWeight=500;nowMs=1;tick();CHECK(gBlankLoadLatched);
 currentWeight=0;nowMs=100;tick();nowMs=600;tick();CHECK(gBlankLoadLatched);
 currentWeight=50;nowMs=650;tick();CHECK(gBlankEmptySinceMs==0);
 currentWeight=0;gHx711Online=false;nowMs=5000;tick();CHECK(gBlankLoadLatched&&gBlankEmptySinceMs==0);
 gHx711Online=true;nowMs=5100;tick();nowMs=5500;tick();nowMs=5799;tick();CHECK(gBlankLoadLatched);gBlankFlowActive=true;nowMs=5800;tick();CHECK(!gBlankLoadLatched&&gBlankFlowRemoved&&gAssignmentRecoveryPending);
 gBlankLoadLatched=true;gBlankLoadWasPresent=false;currentWeight=0;nowMs=10000;tick();nowMs=11000;tick();CHECK(gBlankLoadLatched);
 currentWeight=500;nowMs=11001;tick();currentWeight=0;nowMs=12000;tick();nowMs=12350;tick();nowMs=12700;tick();CHECK(!gBlankLoadLatched);
 // A lagging display cannot prevent real removal or fake a new placement.
 gBlankLoadLatched=true;gBlankLoadWasPresent=true;currentWeight=500;
 nowMs=20000;gBlankLoadSampleWeight=0;gBlankLoadSampleMs=nowMs;blankLoadTick();
 nowMs=20350;gBlankLoadSampleMs=nowMs;blankLoadTick();nowMs=20700;gBlankLoadSampleMs=nowMs;blankLoadTick();CHECK(!gBlankLoadLatched);CHECK(!blankLoadPresent());
 gBlankLoadSampleWeight=500;CHECK(blankLoadPresent());nowMs+=301;CHECK(!blankLoadPresent());
 // A stale zero sample cannot itself finish an empty interval.
 gBlankLoadLatched=true;gBlankLoadWasPresent=true;currentWeight=0;gHx711Online=true;nowMs=25000;tick();
 nowMs=25700;blankLoadTick();CHECK(gBlankLoadLatched&&gBlankEmptySinceMs==0);
 nowMs=25800;tick();CHECK(gBlankLoadLatched&&gBlankEmptySinceMs==25800);
 // Unsigned sample-time arithmetic survives the millis() wrap.
 gBlankLoadLatched=true;gBlankLoadWasPresent=true;gBlankEmptySinceMs=0;nowMs=0xFFFFFF00u;tick();
 nowMs=94;tick();nowMs=444;tick();CHECK(!gBlankLoadLatched);
 // RF-cache expiry/new UIDs cannot reopen a latched physical load.
 resetReaders();gBlankLoadLatched=true;gBlankTagNoticePending=false;gBlankTagUid[0]="";gBlankTagUid[1]="";
 String out;uint8_t streak=0;nowMs=30000;scale.raw=gBlankLoadSampleWeight=500;gBlankLoadSampleMs=nowMs;CHECK(pollRFIDReader(rfid1,out,0,0,"test",streak).empty());CHECK(!gBlankTagNoticePending);
 rfid1.present=false;nowMs=30100;pollRFIDReader(rfid1,out,0,0,"test",streak);nowMs=32000;pollRFIDReader(rfid1,out,0,0,"test",streak);CHECK(gBlankTagUid[0].empty()&&gReaderTagState[0]==0);
 rfid1.present=true;nowMs=32100;pollRFIDReader(rfid1,out,0,0,"test",streak);CHECK(!gBlankTagNoticePending);
 gBlankLoadLatched=false;gBlankTagUid[0]="";nowMs=32200;gBlankLoadSampleMs=nowMs;pollRFIDReader(rfid1,out,0,0,"test",streak);CHECK(gBlankTagNoticePending);
 // Failed/unknown headers cannot become metadata UIDs, even with stale
 // lastUID entries; erasure invalidates RAM and NVS brand caches.
 resetReaders();gBlankTagUid[0]="";gBlankTagNoticePending=false;lastUID=rfid1.identity;rfid1.readable=false;
 CHECK(pollRFIDReader(rfid1,out,0,0,"test",streak).empty()&&out.empty());CHECK(!gBlankTagNoticePending);
 rfid1.readable=true;gMetaCache[rfid1.identity]=1;nvsCache[rfid1.identity]=1;nowMs=33000;gBlankLoadSampleMs=nowMs;
 CHECK(pollRFIDReader(rfid1,out,0,0,"test",streak).empty());CHECK(gBlankTagNoticePending);CHECK(lastUID.empty());CHECK(!gMetaCache.count(rfid1.identity)&&!nvsCache.count(rfid1.identity));
 resetReaders();gBlankTagUid[0]="";rfid1.mem[16]=0x11;CHECK(pollRFIDReader(rfid1,out,0,0,"test",streak).empty());CHECK(gReaderTagState[0]==1);
 resetReaders();gBlankTagUid[0]="";rfid1.mem[16]=0xBC;rfid1.mem[17]=0x0F;rfid1.mem[18]=0xCB;rfid1.mem[19]=0x97;
 CHECK(pollRFIDReader(rfid1,out,0,0,"test",streak)==rfid1.identity);CHECK(gReaderTagState[0]==2);
 // Removing a spool also clears a one-tag waiting state before any picker.
 gBlankTagNoticePending=true;gBlankLoadLatched=false;gBlankLoadWasPresent=true;currentWeight=0;nowMs=34000;tick();nowMs=34350;tick();nowMs=34700;tick();CHECK(!gBlankTagNoticePending);
 // Actual paginated list: opaque tokens are escaped, and a missing final
 // token is empty, never the Arduino String conversion's literal "null".
 pages={R"({"documents":[{"name":"db/inventory/TigerData_abc","updateTime":"version","fields":{"id_type":{"integerValue":"142"},"color_r":{"integerValue":"255"},"name":{"stringValue":"Red"}}},{"name":"db/inventory/04112233445566","fields":{"id_type":{"integerValue":"142"}}}],"nextPageToken":"opaque+/="})",R"({"documents":[{"name":"db/inventory/CLOUD_def","updateTime":"version2","fields":{"id_type":{"integerValue":"142"},"color_b":{"integerValue":"255"}}}]})"};
 InventoryRequest listed;listed.owner="owner";inventoryList(listed);CHECK(listed.ok&&listed.spools.size()==2&&requests.size()==2);
 CHECK(requests[1].find("pageToken=opaque%2B%2F%3D")!=std::string::npos);CHECK(listed.spools[0].id=="TigerData_abc"&&listed.spools[1].id=="CLOUD_def");
 requests.clear();pages={R"({"documents":[{"name":"db/inventory/TIGERDATA_9000000031","updateTime":"purple-version","fields":{"id_type":{"integerValue":"142"},"protocol":{"stringValue":"TigerTag"},"name":{"stringValue":"PLA+ Purple"},"color_r":{"integerValue":"121"},"color_g":{"integerValue":"62"},"color_b":{"integerValue":"182"}}}]})"};
 InventoryRequest purple;purple.owner="owner";inventoryList(purple);CHECK(purple.ok&&purple.spools.size()==1);
 CHECK(purple.spools[0].label.find("#")==std::string::npos&&purple.spools[0].label.find("9000000031")==std::string::npos);
 CHECK(purple.spools[0].id=="TIGERDATA_9000000031"&&purple.spools[0].version=="purple-version"&&purple.spools[0].rgb==0x793EB6);
 // Retrying a partially populated request starts from an empty list.
 requests.clear();inventoryList(purple);CHECK(purple.ok&&purple.spools.size()==1);
 // Clear aspects on either slot use the B/W rail even with a colored swatch;
 // translucent colored filament and records without an aspect stay colored.
 requests.clear();pages={R"({"documents":[{"name":"db/inventory/CLOUD_clear1","fields":{"id_type":{"integerValue":"142"},"id_aspect1":{"integerValue":"21"},"color_r":{"integerValue":"255"}}},{"name":"db/inventory/CLOUD_clear2","fields":{"id_type":{"integerValue":"142"},"id_aspect2":{"integerValue":"21"},"online_color":{"stringValue":"#00FF00"}}},{"name":"db/inventory/CLOUD_translucent","fields":{"id_type":{"integerValue":"142"},"id_aspect1":{"integerValue":"67"},"color_r":{"integerValue":"255"}}},{"name":"db/inventory/CLOUD_basic","fields":{"id_type":{"integerValue":"142"},"color_b":{"integerValue":"255"}}}]})"};
 InventoryRequest clearList;inventoryList(clearList);CHECK(clearList.ok&&clearList.spools.size()==4);
 CHECK(requests[0].find("mask.fieldPaths=id_aspect1")!=std::string::npos&&requests[0].find("mask.fieldPaths=id_aspect2")!=std::string::npos);
 for(int i=0;i<4;i++){auto& s=clearList.spools[i];bool clear=i<2;CHECK(inventoryMatches(s,"",1)==clear);CHECK(inventoryMatches(s,"",2)!=clear);CHECK(s.rgb!=0);}
 CHECK(clearList.spools[0].id=="CLOUD_clear1"&&clearList.spools[0].rgb==0xFF0000&&clearList.spools[1].id=="CLOUD_clear2"&&clearList.spools[1].rgb==0x00FF00);
 // Live Polymaker PVB Clear is catalogued as Basic, with a beige RGB swatch.
 requests.clear();pages={R"({"documents":[{"name":"db/inventory/TigerData_91607937","fields":{"id_type":{"integerValue":"142"},"id_material":{"integerValue":"45962"},"name":{"stringValue":"Clear"},"id_aspect1":{"integerValue":"104"},"id_aspect2":{"integerValue":"255"},"color_r":{"integerValue":"232"},"color_g":{"integerValue":"217"},"color_b":{"integerValue":"195"},"color_a":{"integerValue":"255"}}},{"name":"db/inventory/CLOUD_named","fields":{"id_type":{"integerValue":"142"},"color_name":{"stringValue":"  cLeAr  "},"color_r":{"integerValue":"255"}}},{"name":"db/inventory/CLOUD_red","fields":{"id_type":{"integerValue":"142"},"name":{"stringValue":"Transparent Red"},"id_aspect1":{"integerValue":"67"},"color_r":{"integerValue":"255"}}},{"name":"db/inventory/CLOUD_blue","fields":{"id_type":{"integerValue":"142"},"color_name":{"stringValue":"Clear Blue"},"color_b":{"integerValue":"255"}}}]})"};
 gMaterialDb[45962]="PVB";InventoryRequest namedClear;inventoryList(namedClear);CHECK(namedClear.ok&&namedClear.spools.size()==4);
 CHECK(namedClear.spools[0].id=="TigerData_91607937"&&namedClear.spools[0].rgb==0xE8D9C3&&namedClear.spools[0].material=="PVB");
 CHECK(inventoryMatches(namedClear.spools[0],"PVB",1)&&!inventoryMatches(namedClear.spools[0],"PVB",2));
 for(int i=0;i<4;i++){CHECK(inventoryMatches(namedClear.spools[i],"",1)==(i<2));CHECK(inventoryMatches(namedClear.spools[i],"",2)==(i>=2));}
 requests.clear();pages={"{}"};InventoryRequest empty;inventoryList(empty);CHECK(empty.ok&&empty.spools.empty()&&requests.size()==1);
 requests.clear();pageCode=403;InventoryRequest failed;inventoryList(failed);CHECK(!failed.ok&&failed.spools.empty());pageCode=200;
 // Raw Firestore Values, including unknown nested fields, survive promotion.
 InventoryRequest req;req.source="TigerData_abc";req.owner="owner";req.version="2026-10-24T00:00:00.123456Z";req.uids[0]=uids[0];req.uids[1]=uids[1];memcpy(req.payload,original,144);
 f["timestamp"]["nullValue"]=nullptr;f["id_tigertag"]["doubleValue"]=123;f["last_update"]["timestampValue"]="old";
 f["container_id"]["stringValue"]="paper";number(f,"container_weight",227);number(f,"weight_available",813);
 f["unknown"]["mapValue"]["fields"]["nested"]["arrayValue"]["values"][0]["stringValue"]="preserve";
 f["deleted"]["booleanValue"]=false;f["needUpdateAt"]["booleanValue"]=true;f["deleted_at"]["nullValue"]=nullptr;
 std::string before;serializeJson(f,before);InventoryJson commit(65536);buildCommit(req,f,1792800000,commit);
 CHECK(!commit.overflowed());CHECK(commit["writes"].size()==3);
 for(int i=0;i<2;i++){auto w=commit["writes"][i];auto c=w["update"]["fields"].as<JsonObject>();
 CHECK(inventoryNumber(c,"container_weight")==227&&inventoryNumber(c,"weight_available")==813);CHECK(inventoryText(c,"container_id")=="paper");
 CHECK(c["unknown"]==f["unknown"]);CHECK(!c.containsKey("deleted")&&!c.containsKey("needUpdateAt")&&!c.containsKey("deleted_at"));
 CHECK(c["timestamp"].size()==1&&inventoryNumber(c,"timestamp")==123456);CHECK(c["id_tigertag"].size()==1&&inventoryNumber(c,"id_tigertag")==3155151767.0);
 CHECK(c["last_update"].size()==1);CHECK(inventoryText(c,"twin_tag_uid")==uids[1-i]);CHECK(inventoryNumber(c,"tag_count")==2&&inventoryNumber(c,"tag_index")==i+1);
 CHECK(w["currentDocument"]["exists"]==false);CHECK(w["updateTransforms"][0]["setToServerValue"]=="REQUEST_TIME");}
 CHECK(commit["writes"][2]["currentDocument"]["updateTime"]==req.version.c_str());
 CHECK(commit["writes"][2]["delete"]=="projects/tigertag-connect/databases/(default)/documents/users/owner/inventory/TigerData_abc");
 std::string after;serializeJson(f,after);CHECK(before==after);
 // A newly chosen type is added to both promoted records, without replacing a known type.
 req.containerId="plastic";req.containerWeight=201;commit.clear();buildCommit(req,f,1792800000,commit);
 CHECK(inventoryText(commit["writes"][0]["update"]["fields"],"container_id")=="paper");
 InventoryJson untyped(16384);untyped.set(f);untyped.remove("container_id");untyped.remove("container_weight");
 commit.clear();buildCommit(req,untyped.as<JsonObjectConst>(),1792800000,commit);
 for(int i=0;i<2;i++){auto c=commit["writes"][i]["update"]["fields"].as<JsonObjectConst>();CHECK(inventoryText(c,"container_id")=="plastic"&&inventoryNumber(c,"container_weight")==201);CHECK(c["unknown"]==f["unknown"]);}
 // Existing integer/null Values must be replaced, not combined with the chosen type.
 untyped["container_id"]["nullValue"]=nullptr;untyped["container_weight"]["integerValue"]="133";
 commit.clear();buildCommit(req,untyped.as<JsonObjectConst>(),1792800000,commit);
 for(int i=0;i<2;i++){auto c=commit["writes"][i]["update"]["fields"].as<JsonObjectConst>();CHECK(c["container_id"].size()==1&&c["container_weight"].size()==1);CHECK(inventoryText(c,"container_id")=="plastic"&&inventoryNumber(c,"container_weight")==201);}
 // Repair the old saved request without changing identities, values, or preconditions.
 std::string valid;serializeJson(commit,valid);
 commit["writes"][0]["update"]["fields"]["container_weight"]["integerValue"]="133";
 commit["writes"][1]["update"]["fields"]["container_weight"]["nullValue"]=nullptr;
 commit["writes"][1]["update"]["fields"]["container_id"]["nullValue"]=nullptr;
 CHECK(inventoryRepairContainerValues(commit["writes"].as<JsonArray>()));
 std::string repaired;serializeJson(commit,repaired);CHECK(valid==repaired);
 CHECK(!inventoryRepairContainerValues(commit["writes"].as<JsonArray>()));
 // Legitimate integer-only values on known containers must remain untouched.
 commit.clear();buildCommit(req,f,1792800000,commit);commit["writes"][0]["update"]["fields"]["container_weight"].clear();
 commit["writes"][0]["update"]["fields"]["container_weight"]["integerValue"]="227";
 CHECK(!inventoryRepairContainerValues(commit["writes"].as<JsonArray>()));
 CHECK(inventoryNumber(commit["writes"][0]["update"]["fields"],"container_weight")==227);
 // A four-byte Classic UID (including a tag with cached metadata) is not a TigerTag.
 resetReaders();gBlankTagUid[0]="";rfid1.uid.size=4;rfid1.identity="1234ABCD";
 gMetaCache[rfid1.identity]=1;rfid1.readable=false;gBlankTagNoticePending=false;
 CHECK(pollRFIDReader(rfid1,out,0,0,"test",streak).empty()&&out.empty());
 CHECK(gReaderTagUid[0]=="1234ABCD"&&gReaderTagState[0]==1&&!gBlankTagNoticePending);
 // Other UID lengths/manufacturers must not bypass validation either.
 rfid1.uid.size=7;rfid1.uid.uidByte[0]=0x05;rfid1.readable=true;
 CHECK(pollRFIDReader(rfid1,out,0,0,"test",streak).empty()&&out.empty());
 resetReaders();
 // Authenticated Bambu data is read without any writes; generic Classic is rejected.
 resetReaders();rfid1.uid.size=4;rfid1.sak=8;rfid1.classicAuth=true;
 memcpy(rfid1.classicMem[1],"A00-W1",6);memcpy(rfid1.classicMem[1]+8,"GFA00",5);memcpy(rfid1.classicMem[2],"PLA",3);memcpy(rfid1.classicMem[4],"PLA Basic",9);rfid1.classicMem[5][4]=0xE8;rfid1.classicMem[5][5]=3;float dia=1.75f;memcpy(rfid1.classicMem[5]+8,&dia,4);
 CHECK(probeBambuTag(rfid1,"1234ABCD")&&rfid1.authCalls==2&&rfid1.writeCalls==0);
 rfid1.classicMem[1][8]='X';CHECK(!probeBambuTag(rfid1,"1234ABCD"));
 rfid1.classicAuth=false;CHECK(!probeBambuTag(rfid1,"1234ABCD")&&rfid1.writeCalls==0);
 rfid1.authCalls=0;rfid1.uid.size=7;CHECK(!probeBambuTag(rfid1,"1234ABCD")&&rfid1.authCalls==0);
 resetReaders();
 // A registered tag is distinct from a changed selected inventory record.
 InventoryRequest used;used.uids[0]=uids[0];used.uids[1]=uids[1];used.error=I18N_INV_FAILED;
 requests.clear();pages={"{}"};pageCode=200;checkTargets(used);
 CHECK(!used.ok&&used.error==I18N_INV_TAG_USED&&used.conflictUid==uids[0]);CHECK(requests.size()==1);
 InventoryRequest fresh;fresh.uids[0]=uids[0];fresh.uids[1]=uids[1];requests.clear();pages={"{}","{}"};pageCode=404;checkTargets(fresh);CHECK(fresh.ok&&fresh.conflictUid.empty()&&requests.size()==2);
 InventoryRequest denied;denied.uids[0]=uids[0];denied.uids[1]=uids[1];denied.error=I18N_INV_FAILED;requests.clear();pageCode=403;checkTargets(denied);CHECK(!denied.ok&&denied.error==I18N_INV_FAILED&&denied.conflictUid.empty());pageCode=200;
 InventoryJson selected(4096);selected["updateTime"]="v2";selected["fields"]["id_type"]["integerValue"]="142";
 InventoryRequest changed;changed.source="TigerData_spool";changed.version="v1";requests.clear();checkSource(changed,selected);CHECK(!changed.ok&&changed.error==I18N_INV_CHANGED&&changed.conflictUid.empty()&&requests.empty());
 changed.version="v2";checkSource(changed,selected);CHECK(changed.ok);
 // Releasing an erased pair preserves the old data before UID deletion.
 InventoryJson oa(16384),ob(16384),unassign(65536);oa["updateTime"]="va";ob["updateTime"]="vb";
 oa["fields"].set(f);ob["fields"].set(f);auto af=oa["fields"].as<JsonObject>();auto bf=ob["fields"].as<JsonObject>();
 af["uid"]["stringValue"]=uids[0];bf["uid"]["stringValue"]=uids[1];af["twin_tag_uid"]["stringValue"]=uids[1];bf["twin_tag_uid"]["stringValue"]=uids[0];
 number(af,"tag_index",1);number(bf,"tag_index",2);number(af,"tag_count",2);number(bf,"tag_count",2);number(af,"last_update",100);number(bf,"last_update",200);
 InventoryRequest release;release.owner="owner";release.uids[0]=uids[0];release.uids[1]=uids[1];bool existed[]={true,true};
 std::string oldA,oldB;serializeJson(oa,oldA);serializeJson(ob,oldB);
 CHECK(inventoryBuildRelease(release,oa.as<JsonObjectConst>(),ob.as<JsonObjectConst>(),existed,unassign));CHECK(release.releaseCount==1&&unassign["writes"].size()==3);
 auto kept=unassign["writes"][0]["update"]["fields"].as<JsonObject>();CHECK(inventoryNumber(kept,"weight_available")==813&&inventoryNumber(kept,"container_weight")==227);
 CHECK(kept["unknown"]==f["unknown"]);CHECK(!kept.containsKey("id_tigertag")&&!kept.containsKey("twin_tag_uid")&&!kept.containsKey("tag_index")&&!kept.containsKey("tag_count"));
 CHECK(inventoryNumber(kept,"last_update")==200);CHECK(release.releaseIds[0].startsWith("TigerData_"));CHECK(inventoryText(kept,"uid")==release.releaseIds[0]);
 CHECK(unassign["writes"][0]["currentDocument"]["exists"]==false);CHECK(unassign["writes"][1]["currentDocument"]["updateTime"]=="va"&&unassign["writes"][2]["currentDocument"]["updateTime"]=="vb");
 std::string stillA,stillB;serializeJson(oa,stillA);serializeJson(ob,stillB);CHECK(oldA==stillA&&oldB==stillB);
 number(bf,"weight_available",812);CHECK(inventoryBuildRelease(release,oa.as<JsonObjectConst>(),ob.as<JsonObjectConst>(),existed,unassign));CHECK(release.releaseCount==1&&unassign["writes"].size()==3);
 CHECK(inventoryNumber(unassign["writes"][0]["update"]["fields"],"weight_available")==812);
 af["twin_tag_uid"]["stringValue"]="OTHER_UID";
 CHECK(!inventoryBuildRelease(release,oa.as<JsonObjectConst>(),ob.as<JsonObjectConst>(),existed,unassign));CHECK(release.error==I18N_INV_PAIR_USED&&release.conflictUid=="OTHER_UID");CHECK(unassign["writes"].isNull());
 af["twin_tag_uid"]["stringValue"]=uids[1];existed[1]=false;CHECK(inventoryBuildRelease(release,oa.as<JsonObjectConst>(),ob.as<JsonObjectConst>(),existed,unassign));CHECK(release.releaseCount==1&&unassign["writes"].size()==2);
 existed[0]=false;CHECK(inventoryBuildRelease(release,oa.as<JsonObjectConst>(),ob.as<JsonObjectConst>(),existed,unassign));CHECK(release.releaseCount==0&&unassign["writes"].size()==0);
 existed[0]=true;oa.remove("updateTime");CHECK(!inventoryBuildRelease(release,oa.as<JsonObjectConst>(),ob.as<JsonObjectConst>(),existed,unassign));
 // Resolve lost release responses using full preserved fields, not just IDs.
 deserializeJson(oa,oldA);deserializeJson(ob,oldB);existed[0]=existed[1]=true;CHECK(inventoryBuildRelease(release,oa.as<JsonObjectConst>(),ob.as<JsonObjectConst>(),existed,unassign));
 releaseRequest.clear();serializeJson(unassign,releaseRequest);InventoryJson saved(16384);saved["fields"].set(unassign["writes"][0]["update"]["fields"]);saved["fields"]["updatedAt"]["timestampValue"]="server";
 std::string savedJSON;serializeJson(saved,savedJSON);postCode=-1;requests.clear();pages={"{}","{}",savedJSON};pageCodes={404,404,200};inventoryRelease(release);CHECK(release.ok&&requests.size()==3);
 number(saved["fields"],"weight_available",999);savedJSON.clear();serializeJson(saved,savedJSON);requests.clear();pages={"{}","{}",savedJSON};inventoryRelease(release);CHECK(!release.ok);
 postCode=409;requests.clear();inventoryRelease(release);CHECK(!release.ok&&release.error==I18N_INV_CHANGED&&requests.empty());
 postCode=200;requests.clear();inventoryRelease(release);CHECK(release.ok&&requests.empty());pageCodes.clear();
 // Actual assignment flow: Exit and failed preparation cannot reach writes.
 resetFlow();runInventoryAssignment(false);CHECK(flowWrites==0&&flowPrepares==0&&flowCommits==0);
 resetFlow();flowCancel=true;runInventoryAssignment(false);CHECK(flowWrites==0&&flowPrepares==0);
 resetFlow();flowPick=0;flowContainerOK=false;runInventoryAssignment(false);CHECK(flowWrites==0&&flowPrepares==0&&flowCommits==0);flowContainerOK=true;
 resetFlow();flowPick=0;flowPrepareOK=false;runInventoryAssignment(false);CHECK(flowWrites==0&&flowCommits==0);
 resetFlow();flowPick=0;runInventoryAssignment(false);CHECK(flowWrites==1&&flowCommits==1);CHECK(flowLoading==1&&flowPrepareTitle==I18N_INV_PREPARING);CHECK(flowNotices==0);
 CHECK(gBlankLoadWritten&&gBlankLoadLatched&&gBlankTagUid[0].empty()&&gBlankTagUid[1].empty());
 CHECK(lastUID.empty()&&lastUID2.empty()&&gLastRfidUid1.empty()&&gLastRfidUid2.empty()&&gNextRfidPollMs==0);
 CHECK(gMetaCache.count(rfid1.identity)==0&&nvsCache.count(rfid1.identity)==0&&gMetaCache.count(rfid2.identity)==0&&nvsCache.count(rfid2.identity)==0);
 CHECK(wfPhase==WF_IDLE&&sendPhase=="idle"&&!wfContainerFetched&&!rfidLockedForCurrentLoad&&!autoTarePending&&std::isnan(gLastSentWeight));
 currentWeight=0;nowMs+=100;tick();nowMs+=350;tick();nowMs+=400;tick();CHECK(!gBlankLoadWritten&&!gBlankLoadLatched);
 resetFlow();flowRecover=true;for(int i=0;i<2;i++){auto& reader=i?rfid2:rfid1;memset(reader.mem+16,0,144);reader.mem[16+39]=((i+1)<<4)|2;}runInventoryAssignment(true);CHECK(gBlankLoadWritten&&flowWrites==0&&flowCommits==1&&flowNotices==0);
 resetFlow();flowPick=0;flowRemovedOnCommit=true;runInventoryAssignment(false);CHECK(!gBlankLoadWritten&&gNextRfidPollMs==20000);
 resetFlow();flowPick=0;flowWriteResult=1;runInventoryAssignment(false);CHECK(flowWrites==1&&flowCommits==0&&flowClears==0&&gInventoryAssignmentConflict);CHECK(!gBlankLoadWritten&&gNextRfidPollMs==20000);
 resetFlow();flowPick=0;flowCommitOK=false;runInventoryAssignment(false);CHECK(flowWrites==1&&flowCommits==1&&flowClears==0);CHECK(!gBlankLoadWritten&&gNextRfidPollMs==20000);
 resetFlow();flowUsed=true;flowReleaseAccept=true;runInventoryAssignment(false);CHECK(flowReleases==1&&flowWrites==0&&flowCommits==0);
 // Reuse is conditional on explicit confirmation and a fresh blank pair.
 resetFlow();flowPick=0;flowUsed=true;runInventoryAssignment(false);CHECK(flowReleases==0&&flowWrites==0&&flowCommits==0);
 resetFlow();flowPick=0;flowUsed=true;flowReleaseAccept=true;runInventoryAssignment(false);CHECK(flowReleases==1&&flowPrepares==1&&flowWrites==1&&flowCommits==1);
 resetFlow();flowPick=0;flowUsed=true;flowReleaseAccept=true;rfid2.mem[16]=0xBC;runInventoryAssignment(false);CHECK(flowReleases==0&&flowWrites==0&&flowCommits==0);
 resetFlow();flowPick=0;flowUsed=true;flowReleaseAccept=true;flowReleaseOK=false;runInventoryAssignment(false);CHECK(flowReleases==1&&flowWrites==0&&flowCommits==0);
 resetFlow();flowPick=0;flowListRetry=true;flowListFailures=1;runInventoryAssignment(false);CHECK(flowLoading==2&&flowWrites==1&&flowCommits==1);
 // Erase uses the same bounded writer, but accepts either original NTAG marker.
 uint8_t blankPayload[144]={};resetReaders();
 for(auto r:{&rfid1,&rfid2}){memcpy(r->mem+16,original,144);r->pageCount=0;}
 CHECK(writeInventoryTags(blankPayload,uids,true)==2);
 for(auto r:{&rfid1,&rfid2}){CHECK(memcmp(r->mem+16,blankPayload,144)==0);CHECK(isBlankNtag(*r));CHECK(!r->protectedWrite);}
 resetReaders();rfid2.present=false;CHECK(writeInventoryTags(blankPayload,uids,true)==0&&rfid1.writeCalls==0);
 resetReaders();CHECK(writeInventoryTags(blankPayload,duplicate,true)==0&&rfid1.writeCalls==0);
 resetReaders();rfid2.mem[15]=0x0F;CHECK(writeInventoryTags(blankPayload,uids,true)==0&&rfid1.writeCalls==0);
 CHECK(rfid2.selections==1); // incompatible CC is a hard stop, not a transient read
 resetReaders();rfid1.noUidAttempts=4;CHECK(writeInventoryTags(blankPayload,uids,true)==2);
 resetReaders();rfid2.readFailures=4;CHECK(writeInventoryTags(blankPayload,uids,true)==2);
 for(auto r:{&rfid1,&rfid2})CHECK(memcmp(r->mem+16,blankPayload,144)==0);
 resetReaders();rfid2.readFailures=6;CHECK(writeInventoryTags(blankPayload,uids,true)==0&&rfid1.writeCalls==0&&rfid2.writeCalls==0&&rfid2.selections==6);
 resetReaders();rfid1.noUidAttempts=6;CHECK(writeInventoryTags(blankPayload,uids,true)==0&&rfid1.writeCalls==0&&rfid2.writeCalls==0&&rfid1.selections==6);
 resetReaders();rfid2.identity="OTHER";CHECK(writeInventoryTags(blankPayload,uids,true)==0&&rfid1.writeCalls==0&&rfid2.writeCalls==0&&rfid2.selections==1);
 resetReaders();rfid2.failPage=4;rfid2.failures=1;rfid2.lostAck=true;CHECK(writeInventoryTags(blankPayload,uids,true)==2);
 resetReaders();rfid1.swapAt=2;CHECK(writeInventoryTags(blankPayload,uids,true)==0&&rfid1.writeCalls==0);
 resetReaders();rfid2.failPage=5;CHECK(writeInventoryTags(blankPayload,uids,true)==1);CHECK(isBlankNtag(rfid1));
 resetFlow();pendingFileExists=false;gInventoryAssignmentPending=false;gReaderTagUid[0]=rfid1.identity;gReaderTagUid[1]=rfid2.identity;
 CHECK(detectedTagPairBlank());flowEraseAccept=true;runEraseTags();CHECK(flowWrites==0&&flowNotices==0&&flowEraseQuestions==0);
 gBlankTagUid[1]="";CHECK(!detectedTagPairBlank());
 flowEraseAccept=false;runEraseTags();CHECK(flowWrites==0&&!gBlankLoadLatched);
 flowEraseAccept=true;gReaderTagUid[1]="";runEraseTags();CHECK(flowWrites==0);
 gReaderTagUid[1]=gReaderTagUid[0];runEraseTags();CHECK(flowWrites==0);
 gReaderTagUid[1]=rfid2.identity;gInventoryAssignmentPending=true;runEraseTags();CHECK(flowWrites==0);gInventoryAssignmentPending=false;
 runEraseTags();CHECK(flowWrites==1&&flowCommits==0&&flowReleases==0);CHECK(gBlankLoadLatched&&!gBlankLoadWritten&&lastUID.empty());
 CHECK(gReaderTagState[0]==1&&gReaderTagState[1]==1&&!autoTarePending&&!gBlankFlowActive&&!gLivePaused);
 // Erase prepares the cloud release before writing and commits it only for a verified pair.
 resetFlow();gBlankTagUid[1]="";flowEraseAccept=true;flowUsed=true;runEraseTags();
 CHECK(flowWrites==1&&flowErasePrepared&&flowReleasePrepares==1&&flowReleases==1&&flowReleased);
 CHECK(flowNotices==0&&flowReleaseQuestions==0); // initial erase confirmation covers unlinking
 resetFlow();gBlankTagUid[1]="";flowEraseAccept=true;flowUsed=true;flowWriteResult=1;runEraseTags();
 CHECK(flowWrites==1&&flowReleases==0&&!flowReleased&&flowNotices==1);
 resetFlow();gBlankTagUid[1]="";flowEraseAccept=true;flowUsed=true;flowReleasePrepareOK=false;runEraseTags();
 CHECK(flowWrites==0&&flowReleases==0&&flowNotices==1&&!gBlankFlowActive&&!gLivePaused);
 resetFlow();gBlankTagUid[1]="";flowEraseAccept=true;flowUsed=true;flowCancel=true;runEraseTags();
 CHECK(flowWrites==0&&flowReleases==0&&flowNotices==0&&!gBlankFlowActive&&!gLivePaused);
 resetFlow();gBlankTagUid[1]="";flowEraseAccept=true;flowUsed=true;flowReleaseFailures=1;flowReleaseAccept=true;runEraseTags();
 CHECK(flowWrites==1&&flowReleases==2&&flowReleased&&flowReleasePrepares==2);
 CHECK(flowReleaseQuestions==1&&flowRetryExplained&&flowNotices==0);
 resetFlow();gBlankTagUid[1]="";flowEraseAccept=true;flowUsed=true;flowReleaseOK=false;runEraseTags();
 CHECK(flowWrites==1&&flowReleases==1&&!flowReleased&&flowReleaseQuestions==1&&flowRetryExplained);
 CHECK(flowNotices==0&&detectedTagPairBlank()); // declined retry remains recoverable through lift/place
 pendingFileExists=true;
 // Complete HTTP bodies, bounded retries and non-retryable errors.
 InventoryJson transport(4096);
 httpReplies={{200,"{bad"},{200,R"({"ok":true})"}};httpCalls=0;
 CHECK(testInventoryGet("fixture",transport)==200&&httpCalls==2&&transport["ok"]==true);
 httpReplies={{429,""},{503,""},{200,"{}"}};httpCalls=0;CHECK(testInventoryGet("fixture",transport)==200&&httpCalls==3);
 httpReplies={{-1,""},{-1,""},{-1,""},{200,"{}"}};httpCalls=0;CHECK(testInventoryGet("fixture",transport)==-1&&httpCalls==3);
 httpReplies={{200,"",-3},{200,"{}"}};httpCalls=0;CHECK(testInventoryGet("fixture",transport)==200&&httpCalls==2);
 httpReplies={{403,""},{200,"{}"}};httpCalls=0;CHECK(testInventoryGet("fixture",transport)==403&&httpCalls==1);
 httpReplies={{401,""},{200,"{}"}};httpCalls=refreshes=0;CHECK(testInventoryGet("fixture",transport)==200&&refreshes==1&&httpCalls==2);
 httpReplies={{200,std::string(1024*1024+1,' ')}};httpCalls=0;CHECK(testInventoryGet("fixture",transport)==-100&&httpCalls==1);
 InventoryRequest cancelled;cancelled.cancel=true;gInventoryRequest=&cancelled;httpCalls=0;CHECK(testInventoryGet("fixture",transport)==-1&&httpCalls==0);gInventoryRequest=nullptr;
 // Public catalog requests must never receive the account's bearer token.
 httpReplies={{200,"[]"}};httpCalls=authHeaders=0;CHECK(testInventoryGet("public",transport,false)==200&&authHeaders==0);
 httpReplies={{401,""}};httpCalls=refreshes=0;CHECK(testInventoryGet("public",transport,false)==401&&refreshes==0);
 // Bambu conversion uses native identities and never rewrites existing inventory.
 uint8_t bd[4][16]={};memcpy(bd[0],"A00-W1",6);memcpy(bd[0]+8,"GFA00",5);
 memcpy(bd[1],"PLA",3);memcpy(bd[2],"PLA Basic",9);
 memset(bd[3],255,4);bd[3][4]=0xE8;bd[3][5]=3;bd[3][10]=0xE0;bd[3][11]=0x3F;
 BambuTag bt;CHECK(decodeBambuTag("12345678",bd,bt));
 CHECK(bt.grams==1000&&bt.diameter==1.75f&&bt.rgba==0xFFFFFFFF&&bt.material=="PLA");
 CHECK(bambuInventoryId("abcdef12")=="TigerData_Bambu_ABCDEF12");
 CHECK(bambuInventoryId("XYZ359F0").empty()&&bambuInventoryId("04112233445566").empty());
 BambuTag other=bt;other.uid="ABCDEF12";CHECK(bambuSameProduct(bt,other));
 other.rgba=0;CHECK(!bambuSameProduct(bt,other));
 bd[3][4]=bd[3][5]=0;CHECK(!decodeBambuTag("12345678",bd,other));bd[3][4]=0xE8;bd[3][5]=3;
 bd[3][11]=0x7F;bd[3][10]=0xC0;CHECK(!decodeBambuTag("12345678",bd,other));bd[3][11]=0x3F;bd[3][10]=0xE0;
 bd[1][1]=1;CHECK(!decodeBambuTag("12345678",bd,other));bd[1][1]='L';
 InventoryRequest bi;bi.owner="owner";bi.uids[0]=bt.uid;bi.uids[1]="ABCDEF12";bi.bambu=bt;
 bi.containerId="bambu";bi.containerWeight=249;bi.rawWeight=750;gMaterialDb[38219]="PLA";
 InventoryJson bdoc(16384);auto bfields=bdoc.to<JsonObject>();CHECK(inventoryBambuFields(bi,0,bfields));
 CHECK(inventoryNumber(bfields,"id_brand")==35123&&inventoryNumber(bfields,"id_material")==38219);
 CHECK(inventoryNumber(bfields,"weight_available")==501&&inventoryNumber(bfields,"measure_gr")==1000);
 CHECK(inventoryText(bfields,"online_color")=="#FFFFFFFF"&&!inventoryChipless("TigerData_Bambu_12345678",bfields));
 auto bidentity=inventoryNumber(bfields,"id_tigertag");std::swap(bi.uids[0],bi.uids[1]);
 bdoc.clear();CHECK(inventoryBambuFields(bi,1,bdoc.to<JsonObject>()));
 CHECK(inventoryNumber(bdoc.as<JsonObjectConst>(),"id_tigertag")==bidentity&&inventoryNumber(bdoc.as<JsonObjectConst>(),"tag_index")==1);
 std::swap(bi.uids[0],bi.uids[1]);
 std::vector<std::string> bpages;
 for(int i=0;i<2;i++){bdoc.clear();bdoc["updateTime"]="saved";CHECK(inventoryBambuFields(bi,i,bdoc.createNestedObject("fields")));std::string s;serializeJson(bdoc,s);bpages.push_back(s);}
 pageCode=200;pageCodes={404,404};pages={"{}","{}"};requests.clear();bi.ok=false;inventoryBambuLookup(bi);CHECK(bi.ok&&!bi.found);
 pageCodes.clear();pages=bpages;requests.clear();bi.ok=false;bi.uids[1]="";postedBodies.clear();inventoryBambuLookup(bi);
 CHECK(bi.ok&&bi.found&&bi.uids[1]=="ABCDEF12"&&postedBodies.empty());
 requests.clear();bi.ok=false;bi.uids[1]="12345678";inventoryBambuLookup(bi);CHECK(!bi.ok&&!bi.found);bi.uids[1]="ABCDEF12";
 requests.clear();pageCodes={200,404};bi.ok=false;inventoryBambuLookup(bi);CHECK(!bi.ok&&!bi.found);
 requests.clear();pageCodes={404,200};bi.ok=false;inventoryBambuLookup(bi);CHECK(!bi.ok&&!bi.found);
 requests.clear();pageCodes={403};bi.ok=false;inventoryBambuLookup(bi);CHECK(!bi.ok&&!bi.found);
 bi.bambu.variant="UNKNOWN";pageCodes.clear();requests.clear();pages=bpages;postReplies={-1};postedBodies.clear();bi.ok=false;
 inventoryBambuCreate(bi);CHECK(bi.ok&&bi.found&&postedBodies.size()==1);
 InventoryJson bc(16384);CHECK(!deserializeJson(bc,postedBodies[0]));CHECK(bc["writes"].size()==2);
 for(int i=0;i<2;i++){auto w=bc["writes"][i];CHECK(w["currentDocument"].containsKey("exists")&&!w["currentDocument"]["exists"].as<bool>());CHECK(w["updateTransforms"][0]["setToServerValue"]=="REQUEST_TIME");}
 // An already-created pair reconciles a precondition failure without replacing edits.
 requests.clear();postedBodies.clear();postReplies={409};bi.ok=false;inventoryBambuCreate(bi);CHECK(bi.ok&&bi.found&&postedBodies.size()==1);
 // Verification must release the POST's TLS client before opening another one.
 requests.clear();postedBodies.clear();postReplies={200};bi.ok=false;requireSingleTls=true;
 inventoryBambuCreate(bi);CHECK(bi.ok&&bi.found&&postedBodies.size()==1);CHECK(activeTlsClients==0);requireSingleTls=false;
 // A failed create with neither document saved retries the same conditional batch.
 for(int transient:{-1,408,429,503,401}){
  requests.clear();postedBodies.clear();refreshes=0;bi.ok=false;
  pages={"{}","{}",bpages[0],bpages[1]};pageCodes={404,404,200,200};postReplies={transient,200};
  inventoryBambuCreate(bi);CHECK(bi.ok&&bi.found&&postedBodies.size()==2);
  CHECK(postedBodies[0]==postedBodies[1]);CHECK(refreshes==(transient==401?1:0));
 }
 // Exhaustion, permanent refusal, an unreadable lookup or an occupied twin stops safely.
 requests.clear();postedBodies.clear();bi.ok=false;postReplies={503,503,503,200};
 pages={"{}","{}","{}","{}","{}","{}"};pageCodes={404,404,404,404,404,404};
 inventoryBambuCreate(bi);CHECK(!bi.ok&&!bi.found&&postedBodies.size()==3);
 for(int permanent:{400,403,409,412}){
  requests.clear();postedBodies.clear();bi.ok=false;postReplies={permanent,200};
  pages={"{}","{}"};pageCodes={404,404};inventoryBambuCreate(bi);CHECK(!bi.ok&&postedBodies.size()==1);
 }
 requests.clear();postedBodies.clear();bi.ok=false;postReplies={503,200};pages={"{}"};pageCodes={503};
 inventoryBambuCreate(bi);CHECK(!bi.ok&&postedBodies.size()==1);
 requests.clear();postedBodies.clear();bi.ok=false;pages={"{}",bpages[1]};pageCodes={404,200};
 inventoryBambuCreate(bi);CHECK(!bi.ok&&bi.error==I18N_INV_PAIR_USED&&postedBodies.size()==1);
 pageCodes.clear();pages=bpages;requests.clear();postedBodies.clear();
 postedBodies.clear();bi.cancel=true;bi.ok=false;inventoryBambuCreate(bi);CHECK(!bi.ok&&postedBodies.empty());bi.cancel=false;
 bi.bambu.material="Unknown";inventoryBambuCreate(bi);CHECK(!bi.ok&&postedBodies.empty());bi.bambu=bt;
 bi.rawWeight=100;inventoryBambuCreate(bi);CHECK(!bi.ok&&postedBodies.empty());
 // Exact non-refill SKU mapping and validated live product enrichment.
 bi.bambu=bt;bi.rawWeight=750;
 CHECK(bambuCatalogEntry(bt)&&bambuCatalogEntry(bt)->product==3608667697u);
 other=bt;other.variant="T01-K0";CHECK(!bambuCatalogEntry(other)); // duplicate SKU in the upstream catalog
 other=bt;other.grams=500;CHECK(!bambuCatalogEntry(other));
 InventoryJson productFields(65536),apiFixture(32768);
 std::string productBody=BAMBU_PRODUCT_FIXTURE;
 requests.clear();authenticatedGets.clear();pages={productBody};pageCodes.clear();
 CHECK(inventoryBambuCatalog(bi,productFields)&&requests.size()==1&&!authenticatedGets[0]);
 auto pf=productFields.as<JsonObjectConst>();
 CHECK(inventoryNumber(pf,"id_product")==3608667697u&&inventoryText(pf,"protocol")=="TigerData+");
 CHECK(inventoryText(pf,"name")=="Jade White"&&inventoryText(pf,"sku")=="A00-W1-1.75-1000-spl");
 CHECK(inventoryNumber(pf,"data2")==190&&inventoryNumber(pf,"data3")==230);
 CHECK(!pf.containsKey("weight_available")&&!pf.containsKey("container_id")&&!pf.containsKey("native_uid"));
 CHECK(pf["catalogProduct"]["mapValue"]["fields"]["metadata"]["mapValue"]["fields"]["bambuID"]["stringValue"]=="GFA00");
 CHECK(pf["online_color_list"]["arrayValue"]["values"][0]["stringValue"]=="#FFFFFF");
 CHECK(pf["catalogProduct"]["mapValue"]["fields"]["brand_logo"].containsKey("nullValue"));
 CHECK(!deserializeJson(apiFixture,productBody));
 for(int fault=0;fault<6;fault++){
  deserializeJson(apiFixture,productBody);
  if(fault==0)apiFixture["filament"]["refill"]=true;
  if(fault==1)apiFixture["id"]=1513380430;
  if(fault==2)apiFixture["sku"]="A00-W1-1.75-1000-splfree";
  if(fault==3)apiFixture["filament"]["grams"]=500;
  if(fault==4)apiFixture["brand"]="Other";
  if(fault==5)apiFixture["nozzle"]["temp_max"]=-1;
  std::string bad;serializeJson(apiFixture,bad);requests.clear();pages={bad};
  CHECK(!inventoryBambuCatalog(bi,productFields));
 }
 requests.clear();pages={productBody};CHECK(inventoryBambuCatalog(bi,productFields));
 std::vector<std::string> plusPages;
 for(int i=0;i<2;i++){
  bdoc.clear();deserializeJson(bdoc,bpages[i]);bdoc["updateTime"]="upgraded";
  for(JsonPairConst field:productFields.as<JsonObjectConst>())bdoc["fields"][field.key()].set(field.value());
  std::string savedPlus;serializeJson(bdoc,savedPlus);plusPages.push_back(savedPlus);
 }
 // Upgrade is atomic, masked, versioned and reconciles a lost HTTP response.
 pages={productBody,bpages[0],bpages[1],plusPages[0],plusPages[1]};requests.clear();postedBodies.clear();postReplies={-1};bi.ok=false;
 inventoryBambuUpgrade(bi);CHECK(bi.ok&&bi.productId==3608667697u&&postedBodies.size()==1);
 InventoryJson upgradedCommit(65536);CHECK(!deserializeJson(upgradedCommit,postedBodies[0],DeserializationOption::NestingLimit(96)));
 CHECK(upgradedCommit["writes"].size()==2);
 for(int i=0;i<2;i++){
  auto w=upgradedCommit["writes"][i];auto fields=w["update"]["fields"].as<JsonObjectConst>();
  CHECK(w["currentDocument"]["updateTime"]=="saved");
  CHECK(inventoryNumber(fields,"id_product")==3608667697u);
  CHECK(w["updateMask"]["fieldPaths"].size()==fields.size());
  CHECK(!fields.containsKey("weight_available")&&!fields.containsKey("container_weight")&&!fields.containsKey("twin_tag_uid")&&!fields.containsKey("tags"));
 }
 // Catalog access failure, cancellation and a competing product never write.
 pages={productBody};requests.clear();postedBodies.clear();pageCodes={503};bi.ok=false;inventoryBambuUpgrade(bi);CHECK(!bi.ok&&postedBodies.empty());pageCodes.clear();
 bi.cancel=true;requests.clear();inventoryBambuUpgrade(bi);CHECK(postedBodies.empty());bi.cancel=false;
 deserializeJson(bdoc,bpages[1]);bdoc["fields"]["id_product"]["integerValue"]="123";std::string conflict;serializeJson(bdoc,conflict);
 pages={productBody,bpages[0],conflict};requests.clear();bi.ok=false;inventoryBambuUpgrade(bi);CHECK(!bi.ok&&postedBodies.empty());
 // Conditional conflicts re-read new versions without touching quantity/notes.
 deserializeJson(bdoc,bpages[0]);bdoc["updateTime"]="edited";bdoc["fields"]["weight_available"]["integerValue"]="400";
 bdoc["fields"]["message"]["stringValue"]="User note";std::string edited;serializeJson(bdoc,edited);
 pages={productBody,bpages[0],bpages[1],edited,bpages[1],plusPages[0],plusPages[1]};requests.clear();postReplies={409,200};bi.ok=false;
 inventoryBambuUpgrade(bi);CHECK(bi.ok&&postedBodies.size()==2);
 deserializeJson(upgradedCommit,postedBodies[1],DeserializationOption::NestingLimit(96));CHECK(upgradedCommit["writes"][0]["currentDocument"]["updateTime"]=="edited");
 // Existing Plus records use only the inventory lookup on subsequent placements.
 pages=plusPages;requests.clear();postedBodies.clear();bi.ok=false;bi.productId=0;inventoryBambuLookup(bi);
 CHECK(bi.ok&&bi.productId==3608667697u&&requests.size()==2&&postedBodies.empty());
 // New imports create Plus immediately and keep the measured net weight.
 pages={productBody,plusPages[0],plusPages[1]};requests.clear();postReplies={200};bi.ok=false;inventoryBambuCreate(bi);
 CHECK(bi.ok&&postedBodies.size()==1);deserializeJson(upgradedCommit,postedBodies[0],DeserializationOption::NestingLimit(96));
 auto created=upgradedCommit["writes"][0]["update"]["fields"].as<JsonObjectConst>();
 CHECK(inventoryText(created,"protocol")=="TigerData+"&&inventoryNumber(created,"weight_available")==501);
 CHECK(inventoryNumber(created,"container_weight")==249&&inventoryText(created,"native_uid")==bt.uid);
 // Fresh authentication requires the same physical pair and never writes tags.
 resetFlow();bi.bambu=bt;bi.rawWeight=750;gBlankFlowRemoved=false;
 rfid1.identity=bi.uids[0];rfid2.identity=bi.uids[1];
 for(auto reader:{&rfid1,&rfid2}){reader->uid.size=4;reader->sak=8;reader->classicAuth=true;memcpy(reader->classicMem[1],bd[0],16);memcpy(reader->classicMem[2],bd[1],16);memcpy(reader->classicMem[4],bd[2],16);memcpy(reader->classicMem[5],bd[3],16);}
 CHECK(verifyBambuPair(bi)&&rfid1.writeCalls==0&&rfid2.writeCalls==0);
 rfid1.selections=0;rfid1.noUidAttempts=2;CHECK(verifyBambuPair(bi)&&rfid1.selections==3);
 rfid2.identity="12345678";CHECK(!verifyBambuPair(bi));rfid2.identity=bi.uids[1];
 rfid2.classicMem[5][0]=0;CHECK(!verifyBambuPair(bi));rfid2.classicMem[5][0]=255;
 gBlankFlowRemoved=true;CHECK(!verifyBambuPair(bi));gBlankFlowRemoved=false;
 // Declining import never asks for a container or creates records.
 gBambuTags[0]=bt;gBambuTags[1]=bt;gBambuTags[1].uid=bi.uids[1];gBambuSeenMs[0]=gBambuSeenMs[1]=nowMs;
 flowBambuFound=false;flowBambuCreates=0;flowContainerQuestions=0;runBambuImport();
 CHECK(flowBambuCreates==0&&flowContainerQuestions==0&&gBlankLoadLatched&&!gBlankLoadWritten);
 // A saved pair resolves from one tag without import/container prompts.
 gBambuTags[1]=BambuTag();flowBambuFound=true;runBambuImport();
 CHECK(flowBambuCreates==0&&flowContainerQuestions==0&&gBlankLoadWritten&&gBambuReadyUid[1]==bi.uids[1]);
 CHECK(flowBambuUpgrades==0);
 flowBambuProductId=0;runBambuImport();
 CHECK(flowBambuUpgrades==1&&gBlankLoadWritten&&flowBambuCreates==0);
 flowBambuUpgradeOK=false;runBambuImport();
 CHECK(flowBambuUpgrades==2&&!gBlankLoadWritten&&flowBambuCreates==0);
 flowBambuUpgradeOK=true;flowBambuProductId=3608667697u;
 gBambuTags[0]=gBambuTags[1]=BambuTag();gBambuPending=false;gBambuOwner="";flowBambuFound=false;
 // Container choices use the shared catalog and the account's corrected weights.
 InventoryRequest box;box.source="A";box.owner="owner";
 requests.clear();authenticatedGets.clear();pageCodes.clear();pageCode=200;
 pages={R"({"name":"root/A","updateTime":"va","fields":{"id_brand":{"integerValue":"35123"}}})",
 R"([{"id":"plastic","brand":"Generic","label":"Plastic","brandId":0,"type":"Customizable","container_weight":200},{"id":"bambu","brand":"Bambu Lab","label":"Grey","brandId":35123,"type":"Masterspool","container_weight":249}])",
 R"({"documents":[{"name":"root/containerOverrides/bambu","fields":{"containerWeight":{"doubleValue":253}}}]})"};
 inventoryContainers(box);CHECK(box.ok&&box.version=="va"&&box.containerId.empty()&&box.containers.size()==2);
 CHECK(box.containers[0].id=="bambu"&&box.containers[0].weight==253&&box.containers[1].weight==200);
 CHECK(requests.size()==3&&authenticatedGets[0]&&!authenticatedGets[1]&&authenticatedGets[2]);
 InventoryRequest already;already.source="A";requests.clear();pages={R"({"updateTime":"v2","fields":{"container_id":{"stringValue":"plastic"},"container_weight":{"doubleValue":200}}})"};
 inventoryContainers(already);CHECK(already.ok&&already.containerId=="plastic"&&already.containerWeight==200&&requests.size()==1);
 InventoryRequest stale;stale.source="A";stale.version="old";requests.clear();inventoryContainers(stale);CHECK(!stale.ok&&stale.error==I18N_INV_CHANGED);
 // Updating an existing pair changes only its two container fields, in one conditional commit.
 const std::string noBoxA=R"({"name":"root/A","updateTime":"va","fields":{"twin_tag_uid":{"stringValue":"B"},"weight_available":{"integerValue":"500"}}})";
 const std::string noBoxB=R"({"name":"root/B","updateTime":"vb","fields":{"twin_tag_uid":{"stringValue":"A"}}})";
 box.containerId="plastic";box.containerWeight=200;box.ok=false;
 requests.clear();postedBodies.clear();pages={noBoxA,noBoxB};postReplies={200};inventorySetContainer(box);
 CHECK(box.ok&&postedBodies.size()==1);InventoryJson containerCommit(8192);CHECK(!deserializeJson(containerCommit,postedBodies[0]));
 CHECK(containerCommit["writes"].size()==2);
 for(int i=0;i<2;i++){auto w=containerCommit["writes"][i];auto c=w["update"]["fields"].as<JsonObjectConst>();CHECK(c.size()==2&&inventoryText(c,"container_id")=="plastic"&&inventoryNumber(c,"container_weight")==200);CHECK(w["updateMask"]["fieldPaths"].size()==2);CHECK(w["currentDocument"]["updateTime"]==(i?"vb":"va"));}
 // A lost commit reply reconciles both records instead of issuing a duplicate write.
 const std::string hasBoxA=R"({"name":"root/A","updateTime":"new-a","fields":{"twin_tag_uid":{"stringValue":"B"},"container_id":{"stringValue":"plastic"},"container_weight":{"doubleValue":200}}})";
 const std::string hasBoxB=R"({"name":"root/B","updateTime":"new-b","fields":{"twin_tag_uid":{"stringValue":"A"},"container_id":{"stringValue":"plastic"},"container_weight":{"doubleValue":200}}})";
 box.ok=false;requests.clear();postedBodies.clear();pages={noBoxA,noBoxB,hasBoxA,hasBoxB};postReplies={-1};inventorySetContainer(box);CHECK(box.ok&&postedBodies.size()==1&&requests.size()==4);
 // Existing choices, changed source versions, and unrelated twins are never overwritten.
 box.ok=false;box.containerId="bambu";requests.clear();postedBodies.clear();pages={hasBoxA};inventorySetContainer(box);CHECK(!box.ok&&box.error==I18N_INV_CHANGED&&postedBodies.empty());
 box.containerId="plastic";box.version="old";box.ok=false;requests.clear();pages={noBoxA};inventorySetContainer(box);CHECK(!box.ok&&box.error==I18N_INV_CHANGED&&postedBodies.empty());
 box.version="va";box.ok=false;requests.clear();pages={noBoxA,R"({"name":"root/B","updateTime":"vb","fields":{"twin_tag_uid":{"stringValue":"C"}}})"};inventorySetContainer(box);CHECK(!box.ok&&box.error==I18N_INV_CHANGED&&postedBodies.empty());
 box.cancel=true;box.ok=false;requests.clear();inventorySetContainer(box);CHECK(!box.ok&&requests.empty()&&postedBodies.empty());
 // The normal weighing path asks on an unknown type and uses the chosen tare immediately.
 lastUID=gContainerFetchUID="A";gContainerFetchDone=gContainerFetchMissingType=true;wfContainerFetched=false;gContainerFetchResult=0;flowContainerOK=true;flowContainerQuestions=0;
 pickUpContainer();CHECK(flowContainerQuestions==1&&!gContainerFetchDone&&wfContainerFetched);CHECK(wfContainerWeight==201&&gLastContainer==201&&gContainerBFetchResult==201);
 gContainerFetchDone=true;gContainerFetchMissingType=false;wfContainerFetched=false;gContainerFetchResult=200;pickUpContainer();CHECK(flowContainerQuestions==1&&wfContainerWeight==200);
 gContainerFetchDone=gContainerFetchMissingType=true;wfContainerFetched=false;flowContainerOK=false;rfidLockedForCurrentLoad=false;pickUpContainer();CHECK(wfPhase==WF_DONE&&rfidLockedForCurrentLoad&&sendPhase=="idle"&&sendCountdown==-1);
 gContainerFetchDone=true;gContainerFetchUID="OLD";wfContainerFetched=false;flowContainerQuestions=0;pickUpContainer();CHECK(!wfContainerFetched&&flowContainerQuestions==0);flowContainerOK=true;
 // The actual HSU page writer retries bounded RF errors and lost acknowledgements.
 const uint8_t pageData[]={0x12,0x34,0x56,0x78};
 PageProbe pageOK;pageOK._pn532.codes={0};CHECK(pageOK.writePage(0x27,pageData)&&pageOK._pn532.calls==1&&pageOK.selections==0);
 PageProbe pageRetry;pageRetry._pn532.codes={1,0};CHECK(pageRetry.writePage(0x27,pageData));CHECK(pageRetry._pn532.calls==2&&pageRetry.selections==1&&pageRetry.lastReadPage==0x24);
 PageProbe pageLostAck;pageLostAck._pn532.codes={-2};CHECK(pageLostAck.writePage(4,pageData));CHECK(pageLostAck._pn532.calls==1&&pageLostAck.selections==1&&pageLostAck.lastReadPage==4);
 PageProbe pageMissingAck;pageMissingAck._pn532.codes={-1,0};CHECK(pageMissingAck.writePage(5,pageData)&&pageMissingAck._pn532.calls==2);
 PageProbe pageBadFrame;pageBadFrame._pn532.codes={-3,0};CHECK(pageBadFrame.writePage(5,pageData)&&pageBadFrame._pn532.calls==2);
 PageProbe pageNak;pageNak._pn532.codes={4,0};CHECK(pageNak.writePage(6,pageData)&&pageNak._pn532.calls==2);
 PageProbe pageFailed;pageFailed._pn532.codes={1,1,1};CHECK(!pageFailed.writePage(7,pageData)&&pageFailed._pn532.calls==3&&pageFailed.selections==2);
 PageProbe pageSwapped;pageSwapped._pn532.codes={1,0};pageSwapped.swap=true;CHECK(!pageSwapped.writePage(5,pageData)&&pageSwapped._pn532.calls==1&&pageSwapped.reads==0);
 PageProbe pageGone;pageGone._pn532.codes={1,0};pageGone.present=false;CHECK(!pageGone.writePage(5,pageData)&&pageGone._pn532.calls==1&&pageGone.selections==2);
 PageProbe pageProtected;CHECK(!pageProtected.writePage(3,pageData)&&!pageProtected.writePage(0x28,pageData)&&pageProtected._pn532.calls==0);
 pageProtected.uid.size=0;CHECK(!pageProtected.writePage(5,pageData)&&pageProtected._pn532.calls==0);
 // Actual weight pipeline: two samples rebase, a single spike does not.
 resetWeightFilters();nowMs=100000;scale.raw=0;for(int i=0;i<5;i++){nowMs+=100;readWeight();}
 nowMs+=100;scale.raw=500;CHECK(readWeight()<1);nowMs+=100;scale.raw=0;CHECK(readWeight()<1);
 nowMs+=100;scale.raw=500;CHECK(readWeight()<1);nowMs+=100;CHECK(fabsf(readWeight()-499)<.1f&&gMedianCount==MEDIAN_WINDOW_LARGE);
 nowMs+=100;scale.raw=900;CHECK(fabsf(readWeight()-499)<.1f);nowMs+=100;scale.raw=500;CHECK(fabsf(readWeight()-499)<.1f);
 nowMs+=100;scale.raw=0;CHECK(readWeight()>400);nowMs+=100;CHECK(readWeight()==0&&gMedianCount==MEDIAN_WINDOW_LARGE);
 for(int i=0;i<10;i++){nowMs+=100;scale.raw=(i%2)*.2f;CHECK(readWeight()==0);}
 nowMs+=100;scale.raw=700;readWeight();nowMs+=1000;CHECK(readWeight()<100); // stale candidate cannot confirm
 nowMs+=100;scale.raw=0;readWeight();resetWeightFilters();CHECK(!gEmaInit&&!isfinite(gWeightStepCandidate));
 // A stationary spool near a whole-gram boundary must not alternate 613/614.
 for(int interval:{10,100,200}){
  resetWeightFilters();nowMs+=1000;scale.raw=614.4f;CHECK(lroundf(readWeight())==613);
  for(int i=0;i<200;i++){nowMs+=interval;scale.raw=(i/5)%2?614.9f:614.1f;CHECK(lroundf(readWeight())==613);}
 }
 // Holding a small change must not subtract the dead-zone offset again.
 resetWeightFilters();nowMs+=1000;scale.raw=614.4f;readWeight();
 for(int i=0;i<100;i++){nowMs+=100;scale.raw=614.6f;CHECK(fabsf(readWeight()-613.4f)<.01f);}
 // A sustained one-gram change still registers; large placement/removal stays fast.
 for(int i=0;i<100;i++){nowMs+=100;scale.raw=615.4f;readWeight();}CHECK(lroundf(currentWeight)==614);
 for(int i=0;i<150;i++){nowMs+=100;scale.raw=614.4f;readWeight();}CHECK(lroundf(currentWeight)==613);
 nowMs+=100;scale.raw=900;readWeight();nowMs+=100;CHECK(fabsf(readWeight()-899)<.01f);
 nowMs+=100;scale.raw=0;readWeight();nowMs+=100;CHECK(readWeight()==0);
 // One feedback pulse per distinct physical tag, including blanks and cached twins.
 resetReaders();gBlankTagUid[0]=gBlankTagUid[1]="";gTagReadBeepUid[0]=gTagReadBeepUid[1]="";readBeeps=0;
 nowMs+=100;scale.raw=500;readWeight();
 pollRFIDReader(rfid1,out,0,0,"RIGHT",streak);CHECK(readBeeps==1);
 pollRFIDReader(rfid2,out,0,0,"LEFT",streak);CHECK(readBeeps==2);
 for(int i=0;i<3;i++){nowMs+=100;readWeight();pollRFIDReader(rfid1,out,0,0,"RIGHT",streak);pollRFIDReader(rfid2,out,0,0,"LEFT",streak);}CHECK(readBeeps==2);
 // Losing RF visibility does not re-arm sound; neither does post-write rereading.
 rfid1.present=false;pollRFIDReader(rfid1,out,0,0,"RIGHT",streak);nowMs+=1600;readWeight();pollRFIDReader(rfid1,out,0,0,"RIGHT",streak);
 rfid1.present=true;memcpy(rfid1.mem+16,original,144);pollRFIDReader(rfid1,out,0,0,"RIGHT",streak);CHECK(readBeeps==2);
 // A zero sample or HX711 outage cannot stand in for sustained removal.
 nowMs+=100;scale.raw=0;readWeight();nowMs+=100;scale.raw=500;readWeight();CHECK(!gTagReadBeepUid[0].empty());
 nowMs+=100;scale.raw=0;readWeight();nowMs+=100;readWeight();scale.ready=false;nowMs+=1000;readWeight();scale.ready=true;readWeight();CHECK(!gTagReadBeepUid[0].empty());
 for(int i=0;i<8;i++){nowMs+=100;readWeight();}CHECK(gTagReadBeepUid[0].empty()&&gTagReadBeepUid[1].empty());
 pollRFIDReader(rfid1,out,0,0,"RIGHT",streak);CHECK(readBeeps==2); // removal echo on empty platform
 nowMs+=100;scale.raw=500;readWeight();lastUID=rfid1.identity;lastUIDTwin=rfid2.identity;
 pollRFIDReader(rfid1,out,0,0,"RIGHT",streak);pollRFIDReader(rfid2,out,0,0,"LEFT",streak);CHECK(readBeeps==4);
 // Same UID at the other reader and unreadable headers do not create extra feedback.
 gTagReadBeepUid[0]=gTagReadBeepUid[1]="";gBlankTagUid[0]=gBlankTagUid[1]="";rfid1.readable=false;
 pollRFIDReader(rfid1,out,0,0,"RIGHT",streak);CHECK(readBeeps==4);rfid1.readable=true;
 pollRFIDReader(rfid1,out,0,0,"RIGHT",streak);CHECK(readBeeps==5);rfid2.identity=rfid1.identity;
 pollRFIDReader(rfid2,out,0,0,"LEFT",streak);CHECK(readBeeps==5);
 // A slow RF read refreshes the load before deciding whether to sound.
 gTagReadBeepUid[0]=gTagReadBeepUid[1]="";nowMs+=1000;scale.raw=500;tagReadBeep(rfid1.identity,"RIGHT");CHECK(readBeeps==6);
 gTagReadBeepUid[0]=gTagReadBeepUid[1]="";nowMs+=1000;scale.raw=0;tagReadBeep(rfid1.identity,"RIGHT");CHECK(readBeeps==6);
 {
 // Erasing reciprocal twins never duplicates a spool for weight/backup differences.
 InventoryJson editA(32768),editB(32768),releaseBatch(65536);
 deserializeJson(editA,oldA);deserializeJson(editB,oldB);
 editA["fields"]["rfidBackup"]["booleanValue"]=true;
 editB["fields"]["rfidBackup"]["booleanValue"]=false;
 number(editA["fields"],"weight_available",800);number(editB["fields"],"weight_available",799);
 InventoryRequest keep;keep.owner="owner";keep.uids[0]=uids[0];keep.uids[1]=uids[1];bool bothExist[]={true,true};
 CHECK(inventoryBuildRelease(keep,editA.as<JsonObjectConst>(),editB.as<JsonObjectConst>(),bothExist,releaseBatch));
 CHECK(keep.releaseCount==1&&releaseBatch["writes"].size()==3);
 CHECK(inventoryNumber(releaseBatch["writes"][0]["update"]["fields"],"weight_available")==799);
 editB["fields"]["name"]["stringValue"]="Changed in Studio";
 CHECK(!inventoryBuildRelease(keep,editA.as<JsonObjectConst>(),editB.as<JsonObjectConst>(),bothExist,releaseBatch));
 CHECK(keep.error==I18N_INV_KEEP&&keep.spools.size()==2&&releaseBatch["writes"].isNull());
 keep.releaseChoice=1;
 CHECK(inventoryBuildRelease(keep,editA.as<JsonObjectConst>(),editB.as<JsonObjectConst>(),bothExist,releaseBatch));
 CHECK(keep.releaseCount==1&&inventoryText(releaseBatch["writes"][0]["update"]["fields"],"name")=="Changed in Studio");
 editB["updateTime"]="vb-new";
 CHECK(!inventoryBuildRelease(keep,editA.as<JsonObjectConst>(),editB.as<JsonObjectConst>(),bothExist,releaseBatch));
 CHECK(keep.releaseChoice==-1&&keep.error==I18N_INV_KEEP&&releaseBatch["writes"].isNull());
 keep.releaseChoice=0;editA["fields"]["twin_tag_uid"]["stringValue"]="UNRELATED";
 CHECK(!inventoryBuildRelease(keep,editA.as<JsonObjectConst>(),editB.as<JsonObjectConst>(),bothExist,releaseBatch));
 CHECK(keep.error==I18N_INV_PAIR_USED); // choosing a record cannot steal a third tag
 resetFlow();flowRequireChoice=true;flowPick=1;InventoryRequest chooseRelease;
 CHECK(prepareInventoryRelease(chooseRelease));CHECK(flowReleasePrepares==2&&chooseRelease.releaseChoice==1);
 resetFlow();flowRequireChoice=true;flowPick=-1;InventoryRequest cancelRelease;
 CHECK(!prepareInventoryRelease(cancelRelease));CHECK(cancelRelease.cancel&&flowWrites==0&&flowReleases==0);

 // Rebuild a pending commit from fresh inventory, retaining app-only edits.
 InventoryJson liveSource(32768);deserializeJson(liveSource,oldA);liveSource["updateTime"]="current-version";
 InventoryRequest fresh;fresh.owner="owner";fresh.source="TigerData_source";fresh.version="old-version";
 fresh.uids[0]=uids[0];fresh.uids[1]=uids[1];fresh.stamp=123456;
 CHECK(inventoryEncode(liveSource["fields"],fresh.stamp,fresh.payload));
 number(liveSource["fields"],"weight_available",765);
 liveSource["fields"]["user_note"]["stringValue"]="Keep this app edit";
 auto bodyOf=[](InventoryJson& d){std::string body;serializeJson(d,body);return body;};
 std::string liveBody=bodyOf(liveSource);
 requests.clear();pages={liveBody,"{}","{}"};pageCodes={200,404,404};savedJson.clear();
 fresh.ok=false;inventoryPrepare(fresh,true);CHECK(fresh.ok&&fresh.version=="current-version");
 InventoryJson rebuilt(65536);CHECK(!deserializeJson(rebuilt,savedJson[ASSIGN_COMMIT],DeserializationOption::NestingLimit(96)));
 CHECK(inventoryNumber(rebuilt["writes"][0]["update"]["fields"],"weight_available")==765);
 CHECK(inventoryText(rebuilt["writes"][1]["update"]["fields"],"user_note")=="Keep this app edit");
 CHECK(rebuilt["writes"][2]["currentDocument"]["updateTime"]=="current-version");
 std::string beforeConflict=savedJson[ASSIGN_COMMIT];
 postReplies={200};postedBodies.clear();CHECK(testPostCommit(ASSIGN_COMMIT)==200&&postedBodies.size()==1);
 CHECK(postedBodies[0]==beforeConflict);
 number(liveSource["fields"],"id_material",1234);
 requests.clear();pages={bodyOf(liveSource)};pageCodes={200};fresh.ok=false;
 inventoryPrepare(fresh,true);CHECK(!fresh.ok&&fresh.error==I18N_INV_CHANGED&&requests.size()==1);
 CHECK(savedJson[ASSIGN_COMMIT]==beforeConflict); // material changed: no stale payload or new batch
 requests.clear();pages={"{}"};pageCodes={404};fresh.ok=false;
 inventoryPrepare(fresh,true);CHECK(!fresh.ok&&fresh.error==I18N_INV_CHANGED);

 // The actual worker path recognizes a race as a permanent conflict, not a network retry.
 resetFlow();fresh.op=InventoryRequest::COMMIT;fresh.owner="owner";
 requests.clear();pages={liveBody,liveBody,"{}","{}",liveBody};pageCodes={200,200,404,404,200};
 postCode=412;postCalls=0;pendingFileExists=gInventoryAssignmentPending=true;
 inventoryRun(&fresh);CHECK(!fresh.ok&&fresh.error==I18N_INV_CHANGED&&gInventoryAssignmentConflict);
 CHECK(postCalls==1&&pendingFileExists&&gInventoryAssignmentPending);
 flowRecover=true;runInventoryAssignment(true);CHECK(flowCommits==0&&flowWrites==0&&flowNotices==1);
 // Existing UID records are also a conflict; they cannot be overwritten.
 resetFlow();requests.clear();pages={liveBody,liveBody,"{}"};pageCodes={200,200,200};postCalls=0;
 fresh.op=InventoryRequest::COMMIT;inventoryRun(&fresh);
 CHECK(!fresh.ok&&fresh.error==I18N_INV_TAG_USED&&gInventoryAssignmentConflict&&postCalls==0);
 // Ordinary retry uses current fields and succeeds without programming the tags again.
 resetFlow();requests.clear();pages={liveBody,liveBody,"{}","{}"};pageCodes={200,200,404,404};
 postCode=200;postCalls=0;fresh.op=InventoryRequest::COMMIT;inventoryRun(&fresh);
 CHECK(fresh.ok&&postCalls==1&&!gInventoryAssignmentPending&&!gInventoryAssignmentConflict);

 // A lost successful response reconciles without posting or recreating records.
 InventoryJson appliedA(16384),appliedB(16384);
 appliedA["fields"].set(rebuilt["writes"][0]["update"]["fields"]);
 appliedB["fields"].set(rebuilt["writes"][1]["update"]["fields"]);
 resetFlow();requests.clear();pages={"{}",bodyOf(appliedA),bodyOf(appliedB)};pageCodes={404,200,200};postCalls=0;
 pendingFileExists=gInventoryAssignmentPending=true;fresh.op=InventoryRequest::COMMIT;inventoryRun(&fresh);
 CHECK(fresh.ok&&postCalls==0&&requests.size()==3&&!gInventoryAssignmentPending);
 // A missing source with an incomplete account pair needs explicit reset.
 resetFlow();requests.clear();pages={"{}",bodyOf(appliedA),"{}","{}"};pageCodes={404,200,404,404};postCalls=0;
 pendingFileExists=gInventoryAssignmentPending=true;fresh.op=InventoryRequest::COMMIT;inventoryRun(&fresh);
 CHECK(!fresh.ok&&gInventoryAssignmentConflict&&postCalls==0&&gInventoryAssignmentPending);
 resetFlow();requests.clear();fresh.owner="another-account";fresh.op=InventoryRequest::COMMIT;postCalls=0;
 inventoryRun(&fresh);CHECK(!fresh.ok&&fresh.error==I18N_NO_ACCOUNT&&requests.empty()&&postCalls==0);fresh.owner="owner";

 // Small journals survive restart; legacy selected container data is preserved.
 InventoryJson journal(4096);journal["owner"]="owner";journal["source"]="TigerData_source";
 journal["uid0"]=uids[0];journal["uid1"]=uids[1];journal["stamp"]=fresh.stamp;
 std::string payloadHex;for(uint8_t b:fresh.payload){char h[3];snprintf(h,3,"%02X",b);payloadHex+=h;}journal["payload"]=payloadHex;
 savedJson[ASSIGN_META]=bodyOf(journal);savedJson.erase(ASSIGN_COMMIT);releaseRequest="";
 InventoryRequest restored;CHECK(testReadPending(restored));CHECK(restored.source==fresh.source);
 testMarkConflict();CHECK(gInventoryAssignmentConflict);
 gInventoryAssignmentConflict=false;CHECK(testReadPending(restored)&&gInventoryAssignmentConflict);
 journal["conflict"]=false;savedJson[ASSIGN_META]=bodyOf(journal);
 InventoryJson legacy(4096);legacy["writes"][0]["update"]["fields"]["container_id"]["stringValue"]="legacy-box";
 legacy["writes"][0]["update"]["fields"]["container_weight"]["doubleValue"]=234;
 savedJson[ASSIGN_COMMIT]=bodyOf(legacy);restored=InventoryRequest();CHECK(testReadPending(restored));
 CHECK(restored.containerId=="legacy-box"&&restored.containerWeight==234&&!gInventoryAssignmentConflict);

 // Erase/reset requires the original pair and only clears recovery after full success.
 for(int fault=0;fault<4;fault++){
  resetFlow();flowRecover=flowEraseAccept=true;pendingFileExists=gInventoryAssignmentPending=true;
  gReaderTagUid[0]=rfid1.identity;gReaderTagUid[1]=rfid2.identity;flowUsed=true;
  if(fault==1)gReaderTagUid[1]="OTHER";
  if(fault==2)flowWriteResult=1;
  if(fault==3)flowReleaseOK=false;
  runEraseTags();
  if(!fault){CHECK(flowWrites==1&&flowClears==1&&!gInventoryAssignmentPending&&!pendingFileExists);}
  else {CHECK(flowClears==0&&pendingFileExists&&gInventoryAssignmentPending);}
  if(fault==1)CHECK(flowWrites==0);
  if(fault==2)CHECK(flowReleases==0);
 }
 // A different blank spool cannot route around recovery's original-pair gate.
 resetFlow();gInventoryAssignmentPending=pendingFileExists=true;flowRecover=true;gBlankTagNoticePending=true;
 gBlankTagSeenMs[0]=gBlankTagSeenMs[1]=nowMs;gBlankPairSinceMs=nowMs-1000;
 checkBlankPrompt();CHECK(flowCommits==0&&flowWrites==0&&flowNotices==0&&flowLoading==0&&!gBlankLoadLatched);
 gInventoryAssignmentPending=pendingFileExists=false;flowRecover=false;
 checkBlankPrompt();CHECK(flowLoading==1&&gBlankLoadLatched);
 // Removal must clear the display even with a pending save or late metadata.
 resetFlow();gInventoryAssignmentPending=pendingFileExists=true;gBlankLoadLatched=false;gBlankFlowActive=false;
 currentWeight=500;nowMs=90000;tick();gLastManufacturer="Hatchbox";gLastMaterial="PLA";lastUID="OLD";
 currentWeight=0;nowMs+=100;tick();nowMs+=350;tick();nowMs+=350;tick();
 CHECK(lastUID.empty()&&gLastManufacturer=="--"&&gLastMaterial=="--"&&wfPhase==WF_IDLE);
 CHECK(gInventoryAssignmentPending&&pendingFileExists&&gAssignmentRecoveryPending);
 lastUID="LATE";gLastManufacturer="Hatchbox";nowMs+=100;tick();
 CHECK(lastUID.empty()&&gLastManufacturer=="--");
 // Stale samples must not clear a new load; fresh negative readings still release it.
 currentWeight=500;nowMs+=100;tick();lastUID="ON";gLastManufacturer="Loaded";
 gHx711Online=false;currentWeight=0;nowMs+=1000;tick();CHECK(lastUID=="ON");
 gHx711Online=true;currentWeight=-50;nowMs+=100;tick();nowMs+=350;tick();nowMs+=350;tick();
 CHECK(lastUID.empty()&&gLastManufacturer=="--"&&gInventoryAssignmentPending);

 }
 // A slow NFC transaction must not poison dedup when the weight sample expires.
 resetFlow();lastUID=lastUID2="";gLastRfidUid1="";gLastRfidUid1Ms=0;
 nowMs=300000;gBlankLoadSampleMs=nowMs-500;scale.ready=false;
 CHECK(!acceptRfidUid(rfid1.identity,gLastRfidUid1,gLastRfidUid1Ms,0));CHECK(gLastRfidUid1.empty());
 scale.ready=true;scale.raw=500;
 CHECK(acceptRfidUid(rfid1.identity,gLastRfidUid1,gLastRfidUid1Ms,0));CHECK(gLastRfidUid1==rfid1.identity&&gLastRfidUid1Ms==nowMs);
 CHECK(!acceptRfidUid(rfid1.identity,gLastRfidUid1,gLastRfidUid1Ms,0));
 // Fresh empty readings reject removal echoes without remembering them.
 gLastRfidUid2="";gLastRfidUid2Ms=0;scale.raw=0;nowMs+=100;
 CHECK(!acceptRfidUid(rfid2.identity,gLastRfidUid2,gLastRfidUid2Ms,0));CHECK(gLastRfidUid2.empty());
 // Erase stays disabled through all stages and queued cloud work, then enables once.
 resetFlow();gBlankTagUid[0]=gBlankTagUid[1]="";
 for(int phase:{WF_IDLE,WF_SCANNING,WF_STABLE_WAIT,WF_SENDING}){wfPhase=phase;CHECK(!eraseTagsAvailable());flowEraseAccept=true;runEraseTags();CHECK(flowWrites==0);}
 wfPhase=WF_DONE;CHECK(eraseTagsAvailable());
 for(bool* pending:{&gContainerFetchPending,&gTwinFetchPending,&gCloudSendPending,&gBlankFlowActive}){*pending=true;CHECK(!eraseTagsAvailable());*pending=false;}
 InventoryRequest busy;gInventoryRequest=&busy;CHECK(!eraseTagsAvailable());gInventoryRequest=nullptr;
 wfPhase=WF_IDLE;gInventoryAssignmentPending=true;CHECK(eraseTagsAvailable());gInventoryAssignmentPending=false;gBlankLoadLatched=true;CHECK(eraseTagsAvailable());
 gBlankLoadWritten=true;CHECK(!eraseTagsAvailable());gBlankLoadWritten=false;
 gBlankTagUid[0]=gReaderTagUid[0];gBlankTagUid[1]=gReaderTagUid[1];CHECK(!eraseTagsAvailable());
 // Status text separates identification/lookup from the single weighing stage.
 resetFlow();lastUID="";wfPhase=WF_SCANNING;wfContainerFetched=false;
 CHECK(weighProgressLabel()==I18N_CHECK_TAG_PAIR);
 lastUID="known";CHECK(weighProgressLabel()==I18N_LOADING_SPOOL);
 wfContainerFetched=true;CHECK(weighProgressLabel()==I18N_CHECK_TAG_PAIR);
 wfPhase=WF_STABLE_WAIT;CHECK(weighProgressLabel()==I18N_WEIGHING);
 wfPhase=WF_SENDING;CHECK(weighProgressLabel()==I18N_SENDING);
 gContainerFetchPending=true;CHECK(weighProgressLabel()==I18N_LOADING_SPOOL);gContainerFetchPending=false;
 // Actual scan/stability branches wait for inventory but keep the settle window.
 resetFlow();lastUID="known";lastUID2="twin";wfContainerFetched=false;wfPhase=WF_SCANNING;
 nowMs=400000;wfScanStartMs=nowMs;stableCandidate=NAN;stableSinceMs=0;slopeBufFull=true;wfCurrentSlope=0;
 scanWorkflow(500);CHECK(wfPhase==WF_SCANNING&&gContainerFetchPending&&gContainerFetchUID=="known");
 uint32_t settledFrom=stableSinceMs;nowMs+=9000;scanWorkflow(500);
 CHECK(wfPhase==WF_SCANNING&&stableSinceMs==settledFrom&&weighProgressLabel()==I18N_LOADING_SPOOL);
 gContainerFetchPending=false;gContainerFetchDone=true;gContainerFetchMissingType=false;gContainerFetchResult=200;
 pickUpContainer();scanWorkflow(500);CHECK(wfPhase==WF_STABLE_WAIT&&stableSinceMs==settledFrom);
 CHECK(weighProgressLabel()==I18N_WEIGHING);nowMs+=50;stableWorkflow(500);
 CHECK(wfPhase==WF_SENDING&&stableSinceMs==settledFrom&&weighProgressLabel()==I18N_SENDING);
 resetFlow();wfPhase=WF_SCANNING;lastUID="known";lastUID2="";wfContainerFetched=true;
 wfScanStartMs=nowMs;gTwinFetchDone=true;gTwinFetchResult="twin";
 scanWorkflow(500);CHECK(wfPhase==WF_STABLE_WAIT);
 resetFlow();wfPhase=WF_SCANNING;lastUID=lastUID2="";wfScanStartMs=nowMs-9000;
 scanWorkflow(500);CHECK(wfPhase==WF_IDLE&&currentOledState==OLED_STATE_NO_TAG);
 printf("PASS: %d inventory, reader and weight checks\n",checks);
}
'''
flow_shim=r'''
bool lvglReady=true;bool gInventoryAssignmentPending=false,gInventoryAssignmentConflict=false;
const int WL_CONNECTED=3;struct{int status(){return WL_CONNECTED;}}WiFi;bool gLivePaused=false;uint32_t gLastActivityMs=0;
bool gContainerFetchPending=false,gContainerBFetchDone=false,gCloudSendPending=false,gCloudSendDone=false,gReadyWasZero=false;String gContainerBFetchUID;
bool gContainerFetchDone=false,gContainerFetchMissingType=false;String gContainerFetchUID;
float gContainerFetchResult=0,gContainerBFetchResult=0;
String gLastRfidUid1,gLastRfidUid2,gTwinFetchUID,gTwinFetchResult,gLastRackPosition,gLastRackName,gLastRackId,sendPhase;
uint32_t gLastRfidUid1Ms=0,gLastRfidUid2Ms=0,gLastRfidNoUid1Ms=0,gLastRfidNoUid2Ms=0,gNextRfidPollMs=0,firstUidDetectedMs=0,firstUidPauseUntilMs=0,gCloudWeightSetMs=0,wfWeightPresentSinceMs=0,wfRescanBlockedUntilMs=0,autoTareStableSinceMs=0,autoTareStartedMs=0;
bool gTwinFetchDone=false,gTwinFetchPending=false,rfidLockedForCurrentLoad=false,servoLockedUntilAutotare=false,servoHoldAfterRemoval=false,autoTarePending=false,wfContainerFetched=false;
float gLastContainer=0,gLastSentWeight=NAN,gLastCloudWeight=NAN,wfContainerWeight=0;
int gLastLevel=-1,gLastPosition=-1,sendCountdown=-1,wfPhase=0,currentOledState=0;const int WF_IDLE=0,WF_SCANNING=1,WF_STABLE_WAIT=2,WF_SENDING=3,WF_DONE=4,OLED_STATE_IDLE=0,OLED_STATE_NO_TAG=6;
using LangKey=int;extern InventoryRequest* gInventoryRequest;
void resetSlopeBuffer(){}
bool flowRecover=false,flowRemovedOnCommit=false;int flowNotices=0,flowEraseQuestions=0;
int flowPick=-1,flowWrites=0,flowPrepares=0,flowCommits=0,flowClears=0,flowLoading=0,flowPrepareTitle=-1;
bool flowEraseAccept=false,flowListRetry=false;int flowListFailures=0;
bool flowListOK=true,flowPrepareOK=true,flowCommitOK=true,flowCancel=false;
bool flowUsed=false,flowReleased=false,flowReleaseAccept=false,flowReleaseOK=true;int flowReleases=0;
bool flowRequireChoice=false;bool flowReleasePrepareOK=true,flowErasePrepared=false,flowRetryExplained=false;
bool flowContainerOK=true;int flowContainerQuestions=0;
bool flowBambuFound=false;int flowBambuCreates=0;
uint32_t flowBambuProductId=3608667697u;int flowBambuUpgrades=0;bool flowBambuUpgradeOK=true;
int flowReleasePrepares=0,flowReleaseFailures=0,flowReleaseQuestions=0;
int flowWriteResult=2;
struct lv_obj_t{};int LVCOL_TEXT=0,gFont20=0;
lv_obj_t* lv_scr_act(){static lv_obj_t o;return &o;}
lv_obj_t* lvglCenteredScreen(lv_obj_t** c){*c=lv_scr_act();return lv_scr_act();}
void lvglAddSpinner(lv_obj_t*){}void lvglAddCenteredLabel(lv_obj_t*,const char*,int,const int*){}
void lv_scr_load(lv_obj_t*){}void lv_obj_del(lv_obj_t*){}
void lvglNotice(const char*){flowNotices++;}bool lvglAskYesNo(const char* q,const char* body,int yes=0,int no=0){
 if(!strcmp(q,"move-left")||!strcmp(q,"move-right")){
  repositionDirections.push_back(q);if(repositionAccepts<=0)return false;repositionAccepts--;
  auto& reader=!strcmp(q,"move-right")?rfid1:rfid2;
  if(repositionMode==1){reader.failPage=-1;reader.badBody=reader.badFinal=false;reader.present=true;}
  if(repositionMode==2)reader.identity="OTHER";
  if(repositionMode==3)gBlankFlowRemoved=true;
  return true;
 }
if(!strcmp(q,"erase")||!strcmp(q,"reset"))flowEraseQuestions++;if(!strcmp(q,"release")){flowReleaseQuestions++;if(body&&!strcmp(body,"unlink-failed"))flowRetryExplained=true;}return (!strcmp(q,"list-retry")&&flowListRetry)||((!strcmp(q,"erase")||!strcmp(q,"reset"))&&flowEraseAccept)||(!strcmp(q,"release")&&flowReleaseAccept)||(!strcmp(q,"recover")&&flowRecover);}
const char* t(int key){return key==I18N_TAG_MOVE_LEFT?"move-left":key==I18N_TAG_MOVE_RIGHT?"move-right":key==I18N_INV_RESET?"reset":key==I18N_ERASE_SYNC_FAILED?"unlink-failed":key==I18N_INV_LOAD_RETRY?"list-retry":key==I18N_ERASE_Q?"erase":key==I18N_ERASE_RESULT?"%u/2":key==I18N_TAG_WRITE_RESULT?"%u/%u":key==I18N_INV_RELEASE_Q?"release":key==I18N_INV_RECOVER?"recover":"fixture";}
bool firebaseAuth=true;
bool inventoryReadPending(InventoryRequest& r){r.owner="owner";r.uids[0]=gBlankTagUid[0];r.uids[1]=gBlankTagUid[1];return flowRecover;}
void inventoryClearPending(){flowClears++;gInventoryAssignmentPending=gInventoryAssignmentConflict=pendingFileExists=false;}
void inventoryMarkConflict(){gInventoryAssignmentConflict=true;}
int inventoryPickSpool(std::vector<InventorySpool>&,int=0){return flowPick;}
bool selectSpoolContainer(InventoryRequest& r,bool){flowContainerQuestions++;r.containerWeight=201;return flowContainerOK;}
uint8_t flowWriteTags(const uint8_t* payload,const String*,bool erase=false){flowWrites++;if(erase)flowErasePrepared=flowReleasePrepares>0;for(int i=0;i<flowWriteResult&&i<2;i++){auto& reader=i?rfid2:rfid1;memcpy(reader.mem+16,payload,erase?144:80);if(!erase)reader.mem[16+39]=((i+1)<<4)|2;}return flowWriteResult;}
bool inventoryWait(InventoryRequest& r,int title,bool){
 if(title==I18N_INV_LOADING)flowLoading++;if(r.op==InventoryRequest::PREPARE)flowPrepareTitle=title;
 r.cancel=flowCancel;r.error=I18N_INV_FAILED;
 if(r.op==InventoryRequest::BAMBU_LOOKUP){r.ok=true;r.owner="owner";r.found=flowBambuFound;if(r.found){r.uids[1]="ABCDEF12";r.containerId="bambu";r.productId=flowBambuProductId;}}
 if(r.op==InventoryRequest::BAMBU_UPGRADE){flowBambuUpgrades++;r.ok=flowBambuUpgradeOK;r.productId=3608667697u;}
 if(r.op==InventoryRequest::BAMBU_CREATE){flowBambuCreates++;r.ok=r.found=true;}
 if(r.op==InventoryRequest::LIST){r.spools.clear();InventorySpool s;s.id="TigerData_fixture";s.version="version";r.spools.push_back(s);r.ok=flowListOK;if(flowListFailures>0){flowListFailures--;r.ok=false;}}
 if(r.op==InventoryRequest::PREPARE){flowPrepares++;r.ok=flowPrepareOK;if(flowUsed&&!flowReleased){r.ok=false;r.error=I18N_INV_TAG_USED;}}
 if(r.op==InventoryRequest::PREPARE_RELEASE&&flowRequireChoice&&r.releaseChoice<0){flowReleasePrepares++;r.spools.resize(2);r.error=I18N_INV_KEEP;r.ok=false;return false;}
 if(r.op==InventoryRequest::PREPARE_RELEASE){flowReleasePrepares++;r.releaseCount=flowUsed&&!flowReleased?1:0;r.previousLabel="old spool";r.ok=flowReleasePrepareOK;}
 if(r.op==InventoryRequest::RELEASE){flowReleases++;r.ok=flowReleaseOK;if(flowReleaseFailures>0){flowReleaseFailures--;r.ok=false;}flowReleased=r.ok;}
 if(r.op==InventoryRequest::COMMIT){flowCommits++;r.ok=flowCommitOK;if(flowRemovedOnCommit)gBlankFlowRemoved=true;}
 return r.ok&&!r.cancel;
}
void resetFlow(){gBlankFlowActive=false;gContainerFetchPending=gContainerFetchDone=gTwinFetchPending=gCloudSendPending=gCloudSendDone=false;gBambuTags[0]=gBambuTags[1]=BambuTag();flowRequireChoice=false;gInventoryAssignmentConflict=gInventoryAssignmentPending=pendingFileExists=false;flowReleasePrepareOK=true;flowErasePrepared=flowRetryExplained=false;flowReleasePrepares=flowReleaseFailures=flowReleaseQuestions=0;flowListRetry=false;flowListFailures=0;flowPick=-1;flowWrites=flowPrepares=flowCommits=flowClears=flowLoading=0;flowPrepareTitle=-1;flowListOK=flowPrepareOK=flowCommitOK=true;flowCancel=false;flowWriteResult=2;flowUsed=flowReleased=flowReleaseAccept=false;flowReleaseOK=true;flowReleases=0;flowRecover=flowRemovedOnCommit=false;flowNotices=flowEraseQuestions=0;gBlankFlowRemoved=gBlankLoadWritten=gBlankLoadLatched=false;gHx711Online=true;currentWeight=gBlankLoadSampleWeight=500;gBlankLoadSampleMs=nowMs=10000;resetReaders();gReaderTagState[0]=gReaderTagState[1]=2;gReaderTagUid[0]=rfid1.identity;gReaderTagUid[1]=rfid2.identity;gBlankTagUid[0]=rfid1.identity;gBlankTagUid[1]=rfid2.identity;lastUID=lastUID2=gLastRfidUid1=gLastRfidUid2="STALE";gNextRfidPollMs=20000;wfPhase=4;sendPhase="done";wfContainerFetched=rfidLockedForCurrentLoad=autoTarePending=true;gLastSentWeight=500;for(auto r:{&rfid1,&rfid2}){gMetaCache[r->identity]=1;nvsCache[r->identity]=1;}}
'''

def main():
    includes=list((ROOT/'.pio/libdeps').glob('*/ArduinoJson/src'))
    if not includes: raise SystemExit('Build a PlatformIO environment first to install ArduinoJson.')
    cxx=os.environ.get('CXX') or shutil.which('g++')
    if not cxx:
        candidate=Path.home()/'.platformio/packages/toolchain-gccmingw32/bin/g++.exe'
        if candidate.exists(): cxx=str(candidate)
    if not cxx: raise SystemExit('g++ not found; set CXX to a native C++ compiler.')
    env=os.environ.copy();env['PATH']=str(Path(cxx).parent)+os.pathsep+env.get('PATH','')
    functions=''.join(extract(x) for x in ['static double inventoryNumber(', 'static String inventoryText(', 'static String bambuInventoryId(', 'static bool decodeBambuTag(', 'static bool bambuSameProduct(', 'static bool inventoryChipless(', 'static void inventoryColor(', 'static bool inventoryColorLess(', 'static bool inventoryMatches(', 'static bool inventoryEncode(', 'static String inventoryUrlEncode(', 'static String inventoryDocUrl(', 'static void inventoryList(', 'static bool probeBambuTag(', 'static bool isBlankNtag(', 'static uint8_t writeInventoryTags(', 'static bool inventoryVerifyPair(', 'static bool blankLoadPresent(', 'static void blankLoadTick(', 'static void tagReadBeep(', 'static bool detectedTagPairBlank(', 'static String pollRFIDReader(', 'static bool prepareRfidRead(', 'static bool isDuplicateRecentUid(', 'static bool isUidLatched(', 'static bool acceptRfidUid('])
    erase_flow=extract('static bool eraseTagsAvailable(')+extract('static void runEraseTags(').replace('writeInventoryTags(', 'flowWriteTags(')
    prepare=extract('static void inventoryPrepare(')
    block=prepare.split('    InventoryJson commit(1536 * 1024);\n',1)[1].split('    if (commit.overflowed()',1)[0]
    release_builder=extract('static bool inventoryBuildRelease(')
    release_flow=extract('static bool prepareInventoryRelease(')+extract('static bool releaseInventoryTags(')
    release_commit=extract('static void inventoryRelease(')
    flow=extract('static void restartInventoryRead(')+extract('static bool verifyBambuPair(')+extract('static void runBambuImport(')+extract('static void runInventoryAssignment(').replace('writeInventoryTags(', 'flowWriteTags(')
    containers=extract('static void inventoryContainers(')+extract('static void inventorySetContainer(')+extract('static void inventoryBambuLookup(')+extract('static const BambuCatalogEntry* bambuCatalogEntry(')+extract('static void inventoryCatalogValue(')+extract('static bool inventoryBambuCatalog(')+extract('static void inventoryBambuUpgrade(')+extract('static bool inventoryBambuFields(')+extract('static void inventoryBambuCreate(')
    pickup='void pickUpContainer(){'+extract('if (gContainerFetchDone && !wfContainerFetched) {')+'}\n'
    import re
    keys=sorted(set(re.findall(r'I18N_[A-Z_]+',functions+flow+prepare+tests+release_builder+release_flow+release_commit+erase_flow+containers)))
    target_block=prepare.split('    InventoryJson small(4096);',1)[1].split('    if (r.cancel)',1)[0]
    target_code='void checkTargets(InventoryRequest& r){InventoryJson small(4096);'+target_block+'r.ok=true;}\n'
    source_block=prepare.split('    JsonObjectConst fields = source["fields"];',1)[1].split('    time_t now',1)[0]
    source_code='void checkSource(InventoryRequest& r,InventoryJson& source,bool refresh=false){JsonObjectConst fields=source["fields"];'+source_block+'r.ok=true;}\n'
    performance=performance_shim+extract('static int inventoryGet(').replace('static int inventoryGet(', 'static int testInventoryGet(')
    performance+=''.join(extract(x) for x in ['void resetWeightFilters(', 'static bool isRapidChange(', 'static float applyDeadZone(', 'static float applyHysteresis(', 'static float computeMedian(', 'static bool weightStepConfirmed(', 'float readWeight('])
    rf_method=extract('bool configureRfField(')
    rf_code='''
#define PN532_COMMAND_RFCONFIGURATION 0x32
struct FieldPN{bool ack=true;uint8_t sent[3]={};int timeout=0;bool sendCommandCheckAck(uint8_t* p,size_t n,int t){timeout=t;if(n!=3)return false;memcpy(sent,p,3);return ack;}};
struct FieldProbe{FieldPN _pn532;bool reply=true;uint8_t command=0x33,length=2;int reads=0;bool readResponse(uint8_t* b,size_t,uint8_t& n){reads++;b[0]=0xD5;b[1]=command;n=length;return reply;}
'''+rf_method+'};\n'
    flow_code=flow_shim+extract('static LangKey weighProgressLabel(')+extract('static void clearRemovedSpool(')+release_builder+release_commit+release_flow+flow+erase_flow+target_code+source_code
    builder=extract('static bool inventoryRepairContainerValues(')+'void buildCommit(InventoryRequest& r,JsonObjectConst fields,time_t now,InventoryJson& commit){\n'+block+'}\n'
    page_probe=r'''
#define PN532_COMMAND_INDATAEXCHANGE 0x40
struct PagePN{std::vector<int> codes;int calls=0,code=0;uint8_t memory[144]={};
 bool sendCommandCheckAck(uint8_t* p,size_t n,int){code=calls<(int)codes.size()?codes[calls]:1;calls++;if(n!=8||p[2]!=0xA2||p[3]<4||p[3]>0x27)exit(2);if(code==0||code==-2)memcpy(memory+(p[3]-4)*4,p+4,4);return code!=-1&&code!=-2;}};
struct PageProbe{struct{uint8_t size=7,uidByte[10]={4,1,2,3,4,5,6};}uid;PagePN _pn532;
 int fields=0,selections=0,reads=0,lastReadPage=-1;bool present=true,swap=false;
 bool configureRfField(bool){fields++;return true;}
 bool isNewCardPresent(){selections++;if(swap)uid.uidByte[1]++;return present;}
 bool readCardSerial(){return true;}
 bool readPages16(uint8_t p,uint8_t* bytes){reads++;lastReadPage=p;if(p<4||p+3>0x27)exit(3);memcpy(bytes,_pn532.memory+(p-4)*4,16);return true;}
 bool readResponse(uint8_t* b,size_t,uint8_t& n){if(_pn532.code==-3)return false;n=_pn532.code==4?4:3;b[1]=0x41;b[2]=_pn532.code==1?1:0;b[3]=4;return true;}
'''+extract('bool writePage(')+'};\n'
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True,prefix='tigerscale-inventory-') as folder:
        cpp=Path(folder)/'inventory.cpp';exe=Path(folder)/('inventory.exe' if os.name=='nt' else 'inventory')
        fixture='const char* BAMBU_PRODUCT_FIXTURE=R"JSON('+ (ROOT/'scripts/fixtures/bambu-pla-basic-white.json').read_text(encoding='utf-8') + ')JSON";\n'
        fixture+='const char* TAG_ENCODING_FIXTURE=R"JSON('+ (ROOT/'scripts/fixtures/tigertag-encoding.json').read_text(encoding='utf-8') + ')JSON";\n'
        actual_recovery=extract('static int inventoryPostCommit(').replace('static int inventoryPostCommit(', 'static int testPostCommit(')+extract('static void inventoryPrepare(')+extract('static bool inventoryReconcile(')+extract('static void inventoryPrepareRelease(')+extract('static void inventoryRun(')+extract('static void inventoryMarkConflict(').replace('static void inventoryMarkConflict(', 'static void testMarkConflict(')+extract('static bool inventoryReadPending(').replace('static bool inventoryReadPending(', 'static bool testReadPending(')
        workflow_code=r"""
bool slopeBufFull=true,servoEnabled=false,hwMotorConnected=false;float wfCurrentSlope=0,stableCandidate=NAN;
uint32_t stableSinceMs=0,wfScanStartMs=0,wfStableWaitStartMs=0,oledStateChangeMs=0;
const float SLOPE_STABLE_G_PER_S=5,STABLE_EPSILON_G=.8f;
const uint32_t STABLE_WINDOW_MS=1200,STABLE_WAIT_TIMEOUT_MS=15000,SPOOL_SCAN_DURATION_MS=8000,NO_MOTOR_UID_WAIT_MS=8000,NO_UID_RESCAN_COOLDOWN_MS=2500;
void stopServoSearch(){}void pushSessionEvent(const char*,const String&,float){}
"""+extract('static bool updateStableWindow(')
        workflow_code+='void scanWorkflow(float w){const uint32_t now=millis();'+extract('if (wfPhase == WF_SCANNING) {')+'}\n'
        workflow_code+='void stableWorkflow(float w){const uint32_t now=millis();'+extract('if (wfPhase == WF_STABLE_WAIT) {')+'}\n'
        blank_gate='void checkBlankPrompt(){'+extract('if (!gZeroRequired && !gInventoryAssignmentConflict && !gInventoryAssignmentPending && gBlankTagNoticePending')+'}\n'
        cpp.write_text(shim+'enum {'+','.join(keys)+'};\n'+fixture+functions+rf_code+flow_code+builder+performance+containers+pickup+page_probe+actual_recovery+workflow_code+blank_gate+tests,encoding='utf-8')
        cmd=[cxx,'-std=c++11','-I'+str(includes[0]),'-I'+str(ROOT/'TigerTagSplashESP32'),str(cpp),'-o',str(exe)]
        if os.name=='nt':cmd.insert(1,'-static')
        subprocess.run(cmd,check=True,env=env);subprocess.run([str(exe)],check=True,env=env)
if __name__=='__main__':main()
