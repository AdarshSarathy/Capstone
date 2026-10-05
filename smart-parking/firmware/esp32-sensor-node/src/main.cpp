#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// WiFi Credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// API Endpoint
const char* api_url = "http://192.168.1.100:8000/api/v1/sensors/event";
const char* slot_id = "00000000-0000-0000-0000-000000000001"; // UUID

// Pins
const int trigPin = 5;
const int echoPin = 18;
const int servoPin = 19;

// State
long duration;
float distance_cm;
bool is_occupied = false;
unsigned long last_state_change = 0;
const unsigned long debounce_delay = 1500; // 1500ms debounce filter

Servo gateServo;

void setup() {
  Serial.begin(115200);
  
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  
  gateServo.attach(servoPin);
  gateServo.write(0); // Closed position
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi");
}

void sendEvent(float dist) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(api_url);
    http.addHeader("Content-Type", "application/json");
    
    StaticJsonDocument<200> doc;
    doc["slot_id"] = slot_id;
    doc["distance_cm"] = dist;
    
    String requestBody;
    serializeJson(doc, requestBody);
    
    int httpResponseCode = http.POST(requestBody);
    
    if (httpResponseCode > 0) {
      Serial.printf("HTTP Response code: %d\n", httpResponseCode);
    } else {
      Serial.printf("Error code: %d\n", httpResponseCode);
    }
    http.end();
  }
}

void loop() {
  // Trigger sensor
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  duration = pulseIn(echoPin, HIGH, 30000); // 30ms timeout
  if (duration == 0) {
    distance_cm = 400.0; // max range
  } else {
    distance_cm = duration * 0.034 / 2;
  }
  
  bool current_reading = (distance_cm < 15.0);
  
  if (current_reading != is_occupied) {
    if (millis() - last_state_change > debounce_delay) {
      is_occupied = current_reading;
      last_state_change = millis();
      Serial.printf("State changed. Occupied: %d, Distance: %.1f cm\n", is_occupied, distance_cm);
      sendEvent(distance_cm);
    }
  } else {
    last_state_change = millis();
  }
  
  delay(100);
}
