#include "arduino.h"

void sendCommand(String command) {
    Serial1.println(command);
    Serial.println(command);
    delay(1000);
//    Serial1.println("G:");
    if (Serial1.available()) {
        String response = Serial1.readStringUntil('\n');
        response.trim();
        Serial.print("GSC-01 Response 1: ");
        Serial.println(response);
        if(response == "OK") {
          Serial1.println("G:");
          delay(1000);
//          Serial.println(Serial1.readString());
        }
        else {
          Serial.println("Wrong");
        }
    } else {
        Serial.println("No response from GSC-01.");
    }
}

void moveRelative(long steps) {
    String direction = (steps >= 0) ? "+" : "-";
    sendCommand("M:1" + direction + "P" + String(abs(steps)));
//    delay(1000);
    
//    waitForMotor(); // wait for motor finish
}

void moveAbsolute(long steps) {
    String direction = (steps >= 0) ? "+" : "-";
    sendCommand("A:1" + direction + "P" + String(abs(steps)));
//    delay(1000);
//    waitForMotor();  // wait for motor finish
}

void jogMove(String direction) {
    if (direction == "+" || direction == "-") {
        sendCommand("J:1" + direction);
//        delay(1000);
         
    } else {
        Serial.println("Invalid direction! Use '+' or '-'.");
    }
}

void setJogSpeed(int speed){
     if (speed >= 100 && speed <= 20000) {  // Validate speed range
         String command = "S:J" + speed;  // Create command string
         Serial1.println(command);  // Send to Serial1
         Serial.println("Command Sent: " + command);  // Feedback
     } else {
         Serial.println("Error: Speed must be between 100 and 20,000 PPS.");
   }
}
void returnJogSpeed(){
    Serial.println("Jogging speed: ");
    delay(1000);
    Serial1.println("V:J");
    Serial.println(Serial1.readString());
}
void setSpeed(String command){ // command format; SET SPEED S100F500R200
   // Validate command format
    if (command.startsWith("SET SPEED ") && command.indexOf('S') > 10 && command.indexOf('F') > 11 && command.indexOf('R') > 12) {
            
            // Extract parameter positions
            int sIndex = command.indexOf('S') + 1;
            int fIndex = command.indexOf('F') + 1;
            int rIndex = command.indexOf('R') + 1;

            int minSpeed = command.substring(sIndex, fIndex - 1).toInt();
            int maxSpeed = command.substring(fIndex, rIndex - 1).toInt();
            int accelTime = command.substring(rIndex).toInt();

            // Validate range
            if (minSpeed < 100) minSpeed = 100;
            if (minSpeed > 20000) minSpeed = 20000;
            if (maxSpeed < 100) maxSpeed = 100;
            if (maxSpeed > 20000) maxSpeed = 20000;
            if (accelTime < 0) accelTime = 0;
            if (accelTime > 1000) accelTime = 1000;

            // Ensure max speed is higher than min speed
            if (maxSpeed <= minSpeed) {
                Serial.println("NG");  // Invalid speed order
                return;
            }

            // Round speeds to nearest 100 PPS
            minSpeed = (minSpeed / 100) * 100;
            maxSpeed = (maxSpeed / 100) * 100;

            // Print extracted values
            Serial.print("Min Speed (S): ");
            Serial.println(minSpeed);
            Serial.print("Max Speed (F): ");
            Serial.println(maxSpeed);
            Serial.print("Acceleration Time (R): ");
            Serial.println(accelTime);
            Serial.println("OK");  // Successfully processed
            String configSpeed = "D:1S"+ String(minSpeed) +"F" + String(maxSpeed) +"R" + String(accelTime);
            Serial1.println(configSpeed);
            Serial.println(configSpeed); 
        } else {
            Serial.println("NG");  // Invalid format
        }
    }
void motorFree(String command){
    if (command.startsWith("MOTOR FREE ")) {
    char mode = command.charAt(11);  // Extract the last character (should be '0' or '1')
    // Validate mode ('0' = free motor, '1' = hold motor)
        if (mode == '0' || mode == '1') {
            String command = "C:1" + String(mode);  // Convert to controller format
            Serial1.println(command);  // Send formatted command
            Serial.println(command);
            Serial.println("OK");  // Successfully processed
            } else {
                Serial.println("NG");  // Invalid mode
            }
        } else {
            Serial.println("NG");  // Invalid format
        }
    }
void stopMotor(){
  Serial.println("Stop...");
  Serial1.println("L:1");
//  Serial1.println("Q:");
  Serial.println(Serial1.readString());
}
void eStop(){
  Serial.println("Emergency Stop");
  Serial1.println("L:E");
//  Serial1.println("Q:");
  Serial.println(Serial1.readString());
}
void moveToOrigin() {
    Serial.println("Moving to Origin...");
    Serial1.println("H:1");
    delay(1000);
//    waitForMotor();
    Serial.println("Motor reset: "+ Serial1.readString());
}
void waitForMotor() {
    Serial.println("Waiting for motor to finish...");

    while (true) {
        Serial1.println("!:");  // Send code to check condition
        delay(1000);

        if (Serial1.available()) {
            String response = Serial1.readStringUntil('\n');
            response.trim();
            Serial.print("Motor Status: ");
            Serial.println(response);
            if (response == "R") {
                Serial1.println("Q:");
                delay(500);
                Serial.println(Serial1.readString());
                Serial.println("Ready for next move");
                break; 
            }
        }
    }
}
void checkStatus(){
  Serial.println("Current Status: ");
  Serial1.println("Q:");
  Serial.println(Serial1.readString());
}
void receiveResponse() {
    if (Serial1.available()) {  // Check if Serial1 has data
        String response = Serial1.readStringUntil('\n');  // Read response
        response.trim();  // Remove extra spaces or newline

        if (response == "OK") {
            Serial.println("Received: OK");  // Successfully received
        } else if (response == "NG") {
            Serial.println("Received: NG");  // Error received
        } else {
            Serial.print("Unknown Response: ");
            Serial.println(response);  // Print any unexpected response
        }
    }
}
float calculateAngle(long steps) {
    // Calculate the angle based on the provided step value
    if (steps <= 144000) {
        return (steps * 0.0025);  // If steps are less than or equal to 144000, use a simple conversion
    } else {
        int round = steps / 144000;
        return (steps - round*144000) * 0.0025;  // Apply the formula for steps greater than 144000
    }
}
void getCurrentAngle() {
    Serial.println("Requesting Current Angle...");

    Serial1.println("Q:");
    delay(500);  // Wait for the response from GSC-01

    // Check if data is available from the serial interface
    if (Serial1.available()) {
        String response = Serial1.readStringUntil('\n');
        response.trim();

        // Split the response string to get the step number
        long spaceIndex = response.indexOf(','); 
        if (spaceIndex != -1) {
            String stepsStr = response.substring(0, spaceIndex); // Extract steps value
            long steps = stepsStr.toInt(); // Convert to integer

            // Calculate the angle from the steps
            float angle = calculateAngle(steps);

            // Print the results to the Serial Monitor
            Serial.print("Current Position (Steps): ");
            Serial.println(steps);
            Serial.print("Current Angle (Degrees): ");
            Serial.println(angle, 2);  
        } else {
            Serial.println("Invalid response from GSC-01.");
        }
    } else {
        Serial.println("No response from GSC-01.");
    }
}
void speedTest(){
    Serial.println("Speed up");
    Serial1.println("D:1S1000F12000R500");
    delay(100);
    Serial.println(Serial1.readString());
}

void setup() {
    Serial.begin(9600);    // Serial Monitor
    Serial1.begin(9600);   // Set communication with GSC-01
    //Serial1.setTimeout(5000);
    Serial.println("ATmega2560 Connected");
    
    // Move to origin when start
    //    moveToOrigin();
}

void loop() {
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n'); // Read request from Serial
        command.trim();

        
        if (command.startsWith("MOVE_REL ")) {
            long steps = command.substring(9).toInt(); // Take step move
//            Serial.println(steps);
            moveRelative(steps);
        }
       
        else if (command.startsWith("MOVE_ABS ")) {
            long position = command.substring(9).toInt(); // Get absolute value
            moveAbsolute(position);
        }
        
        else if (command == "STOP") {
            stopMotor();
        }
        else if (command == "E"){
            eStop();
        }
        else if (command == "ORIGIN") {
            moveToOrigin();
        }
        else if ( command.startsWith("JOGGING ")) { 
           String direction = command.substring(8);
           jogMove(direction);   
        }
        else if (command.startsWith("JOGGING SPEED ")){
          String speedValue = command.substring(14);
          
        }
        else if (command.startsWith("RETURN JOGGING SPEED")){
          returnJogSpeed();
        } 
        else if (command.startsWith("SET SPEED ")){
          setSpeed(command);
        }
        else if (command.startsWith("STATUS")){
        checkStatus();
        }
        else if ( command.startsWith("ANGLE")){
          getCurrentAngle();
        }
        else if ( command.startsWith("MOTOR FREE ")){
          motorFree(command);
        }
        else if (command.startsWith("SPEED UP")) {
          speedTest();
        }
        else {
          Serial.println("Wrong Command");
        }
       }
    }


    
