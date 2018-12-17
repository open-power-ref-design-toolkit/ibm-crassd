package ipmiSelParser;

/*
 *Copyright 2017 IBM Corporation
*
*   Licensed under the Apache License, Version 2.0 (the "License");
*   you may not use this file except in compliance with the License.
*   You may obtain a copy of the License at
*
*       http://www.apache.org/licenses/LICENSE-2.0
*
*   Unless required by applicable law or agreed to in writing, software
*   distributed under the License is distributed on an "AS IS" BASIS,
*   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
*   See the License for the specific language governing permissions and
*   limitations under the License.
*/

/**
* Base class for BmcEvents. Intended to hold information from the BMC's CerId lookup xml once an event is found
* by the {@link BmcEventParser}
*
*/

public class BmcEvent {
    public static final int SENSOR_LOC = 3;
    public static final int STATE_LOC = 4;
    public static final int DETAILS_LOC = 5;
    public static final int DATE_LOC = 1;
    public static final int TIME_LOC = 2;
    public static final String SEV_CRITICAL = "Critical";
    
    String cerId;
    String sensor;
    String state;
    String addDetails;
    String message;
    boolean serviceable;
    boolean callHome;
    String severity;
    String eventType;
    String vmMigration;
    String subSystem;
    String compInstance;
    String userAction;
    String timestamp;
    
    @Override
    public String toString(){
        String bmcEventText="";
        bmcEventText += "CerID: "+cerId+"\n"+
                "sensor: "+sensor+"\n"+
                "state: "+state+"\n" +
                "additonalDetlails: "+addDetails+"\n" +
                "message: "+message+"\n" +
                "serviceable: "+serviceable+"\n" +
                "callHome: "+callHome+"\n" +
                "severity: "+severity+"\n" +
                "eventType: "+eventType+"\n" +
                "vmMigration: "+vmMigration+"\n" +
                "subSystem: "+subSystem+"\n" +
                "timestamp: "+timestamp+"\n" +
                "userAction: "+userAction;
        return bmcEventText;
    }
    /**
     * @return the cerId
     */
    public String getCerId() {
        return cerId;
    }
    /**
     * @param cerId the cerId to set
     */
    public void setCerId(String cerId) {
        this.cerId = cerId;
    }
    /**
     * @return the sensor
     */
    public String getSensor() {
        return sensor;
    }
    /**
     * @param sensor the sensor to set
     */
    public void setSensor(String sensor) {
        this.sensor = sensor;
    }
    /**
     * @return the state
     */
    public String getState() {
        return state;
    }
    /**
     * @param state the state to set
     */
    public void setState(String state) {
        this.state = state;
    }
    /**
     * @return the addDetails
     */
    public String getAddDetails() {
        return addDetails;
    }
    /**
     * @param addDetails the addDetails to set
     */
    public void setAddDetails(String addDetails) {
        this.addDetails = addDetails;
    }
    /**
     * @return the message
     */
    public String getMessage() {
        return message;
    }
    /**
     * @param message the message to set
     */
    public void setMessage(String message) {
        this.message = message;
    }
    /**
     * @return the serviceable
     */
    public boolean isServiceable() {
        return serviceable;
    }
    /**
     * @param serviceable the serviceable to set
     */
    public void setServiceable(boolean serviceable) {
        this.serviceable = serviceable;
    }
    /**
     * @return the callHome
     */
    public boolean isCallHome() {
        return callHome;
    }
    /**
     * @param callHome the callHome to set
     */
    public void setCallHome(boolean callHome) {
        this.callHome = callHome;
    }
    /**
     * @return the severity
     */
    public String getSeverity() {
        return severity;
    }
    /**
     * @param severity the severity to set
     */
    public void setSeverity(String severity) {
        this.severity = severity;
    }
    /**
     * @return the eventType
     */
    public String getEventType() {
        return eventType;
    }
    /**
     * @param eventType the eventType to set
     */
    public void setEventType(String eventType) {
        this.eventType = eventType;
    }
    /**
     * @return the vmMigration
     */
    public String getVmMigration() {
        return vmMigration;
    }
    /**
     * @param vmMigration the vmMigration to set
     */
    public void setVmMigration(String vmMigration) {
        this.vmMigration = vmMigration;
    }
    /**
     * @return the subSystem
     */
    public String getSubSystem() {
        return subSystem;
    }
    /**
     * @param subSystem the subSystem to set
     */
    public void setSubSystem(String subSystem) {
        this.subSystem = subSystem;
    }
    /**
     * @return the compInstance
     */
    public String getCompInstance() {
        return subSystem;
    }
    /**
     * @param compInstance the compInstance to set
     */
    public void setCompInstance(String compInstance) {
        this.compInstance = compInstance;
    }
    /**
     * @return the userAction
     */
    public String getUserAction() {
        return userAction;
    }

    /**
     * @param userAction the userAction to set
     */
    public void setUserAction(String userAction) {
        this.userAction = userAction;
    }
    public void setTimestamp(String utcTime){
        this.timestamp = utcTime;
    }
    public String toJSON(){
        String json="";
        json += "{\n" +
                "\t\"CerID\": \""+cerId+"\",\n"+
                "\t\"sensor\": \""+sensor+"\",\n"+
                "\t\"state\": \""+state+"\",\n" +
                "\t\"additonalDetails\": \""+addDetails+"\",\n" +
                "\t\"message\": \""+message+"\",\n" +
                "\t\"serviceable\": \""+serviceable+"\",\n" +
                "\t\"callHome\": \""+callHome+"\",\n" +
                "\t\"severity\": \""+severity+"\",\n" +
                "\t\"eventType\": \""+eventType+"\",\n" +
                "\t\"vmMigration\": \""+vmMigration+"\",\n" +
                "\t\"subSystem\": \""+subSystem+"\",\n" +
                "\t\"timestamp\": \""+timestamp+"\",\n" +
                "\t\"compInstance\": \""+compInstance+"\",\n" +
                "\t\"userAction\": \""+userAction + "\"" +
                "\n}";
        return json;
    }
}
