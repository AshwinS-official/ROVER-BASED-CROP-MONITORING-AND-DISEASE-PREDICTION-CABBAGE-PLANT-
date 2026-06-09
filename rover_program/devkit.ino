#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <DHT.h>
#include <esp_wifi.h>
#include "esp_task_wdt.h"

// --- CONFIG ---
const char* ssid = "ASHWIN";
const char* pass = "ALLISWELL";
const char* zrokUrl = "https://dauxr8trt87z.shares.zrok.io/telemetry";

// Pins
#define DHTPIN 13
#define TRIG 5
#define ECHO 18
#define M1 6   // Left Fwd
#define M2 7   // Left Bwd
#define M3 41  // Right Fwd (Set PSRAM to Disabled!)
#define M4 42  // Right Bwd (Set PSRAM to Disabled!)

// Global Shared Variables (Thread Safe)
DHT dht(DHTPIN, DHT11);
volatile float g_core=0, g_amb=0, g_hum=0;
volatile int g_dist=0;
String g_command = "STOP";
unsigned long g_last_packet_time = 0;

void move(String c) {
  if(c=="FORWARD"){digitalWrite(M1,1);digitalWrite(M2,0);digitalWrite(M3,1);digitalWrite(M4,0);}
  else if(c=="BACKWARD"){digitalWrite(M1,0);digitalWrite(M2,1);digitalWrite(M3,0);digitalWrite(M4,1);}
  else if(c=="LEFT"){digitalWrite(M1,0);digitalWrite(M2,1);digitalWrite(M3,1);digitalWrite(M4,0);}
  else if(c=="RIGHT"){digitalWrite(M1,1);digitalWrite(M2,0);digitalWrite(M3,0);digitalWrite(M4,1);}
  else {digitalWrite(M1,0);digitalWrite(M2,0);digitalWrite(M3,0);digitalWrite(M4,0);}
}


void networkTask(void * pvParameters) {
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;

  while(1) {
    if (WiFi.status() == WL_CONNECTED) {
      http.begin(client, zrokUrl);
      http.addHeader("Content-Type", "application/json");
      http.addHeader("Connection", "keep-alive");
      http.setTimeout(1000);

      String json = "{\"core_temp\":" + String(g_core) + ",\"amb_temp\":" + String(g_amb) + 
                    ",\"hum\":" + String(g_hum) + ",\"dist\":" + String(g_dist) + "}";
      
      int res = http.POST(json);
      if (res == 200) {
        g_command = http.getString();
        g_command.trim();
        g_last_packet_time = millis();
        Serial.print("$"); // Telemetry success
      }
      http.end();
    }
    vTaskDelay(200 / portTICK_PERIOD_MS); // Sync 5 times per second
  }
}

void setup() {
 
  setCpuFrequencyMhz(160);
  
  Serial.begin(115200);
  esp_task_wdt_deinit(); 

  pinMode(M1, OUTPUT); pinMode(M2, OUTPUT); pinMode(M3, OUTPUT); pinMode(M4, OUTPUT);
  pinMode(TRIG, OUTPUT); pinMode(ECHO, INPUT);
  dht.begin();

  WiFi.begin(ssid, pass);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  

  WiFi.setTxPower(WIFI_POWER_11dBm);
  Serial.println("\n[S3] PRO-MODE ACTIVE");

  xTaskCreatePinnedToCore(networkTask, "NetTask", 8192, NULL, 1, NULL, 0);
}

void loop() {
 
  static unsigned long lastDHT = 0;
  if (millis() - lastDHT > 3000) {
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) { g_amb = t; g_hum = h; }
    g_core = temperatureRead();
    lastDHT = millis();
  }

  digitalWrite(TRIG, 0); delayMicroseconds(2); digitalWrite(TRIG, 1); delayMicroseconds(10); digitalWrite(TRIG, 0);
  int d = pulseIn(ECHO, 1, 25000) * 0.034 / 2;
  if(d > 0) g_dist = d;

 
  if (millis() - g_last_packet_time > 1500) {
    move("STOP");
  } else {
    move(g_command);
    if(g_command != "STOP") Serial.print("*");
  }

  delay(20); 
}