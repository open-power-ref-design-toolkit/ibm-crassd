/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package ipmiSelParser;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.sql.Timestamp;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 *
 * @author thalerj
 */
public class ipmiSelParser {

    /**
     * @param args the command line arguments
     */
    public static void main(String[] args) {
        long startTime = System.currentTimeMillis();
        String bmcIP = args[0];
        String bmcUser = args[1];
        String bmcPW = args[2];
        BufferedReader ipmiSelList;
        BmcEvent cerEvent = null;
        String line = null;
        
        //get sel list from BMC
            long importStart = System.currentTimeMillis();
            ipmiSelList = getSEL(bmcIP, bmcUser, bmcPW);
            //System.out.println("Import Run Time: " + String.valueOf(System.currentTimeMillis() - importStart) + " ms.");
        /*    
        //process list using xmap
            System.out.println("Parsing SEL....");
            long processTimeStart = System.currentTimeMillis();
            int alertCount = processSels(ipmiSelList);
            long processEndTime = System.currentTimeMillis();
            System.out.println("Processing Run Time: " + String.valueOf(processEndTime - processTimeStart) + " ms.");
            if (alertCount>0){
                System.out.println("Average time per alert: " + String.valueOf((processEndTime - processTimeStart)/alertCount) + " ms.");
            }
        */    
        //process sel list using hash map
        //ipmiSelList = getSEL(bmcIP,bmcUser, bmcPW);
        long processTimeStart = System.currentTimeMillis();
        int alertCount = processSelsHashMap(ipmiSelList);
        long processEndTime = System.currentTimeMillis();
        if (alertCount>0){
            //System.out.println("Total Hash Map Time: " + String.valueOf((processEndTime - processTimeStart)) + " ms.");
        }
        
        //output CER events
        //System.out.println(cerEvent);
        long endTime = System.currentTimeMillis();
        //System.out.println("Total running time: " + String.valueOf(endTime - startTime) + " ms.");
    }
    
    /**
     * Attempt to get the SEL list and return it in a buffered reader. 
     *  
     * @param bmcIP The hostname or ip address of the BMC to get the SEL from
     * @param userName The userName for the BMC to use.
     * @param pw  The password for the BMC userName
     * @return Buffered reader containing a sel list. 
     */
    private static BufferedReader getSEL(String bmcIP, String userName, String pw){
        String ipmiCommand = "ipmitool -I lan -H " +bmcIP + " -U " + userName + " -P " +pw + " sel list";
        ProcessBuilder pb = new ProcessBuilder("bash","-c",ipmiCommand);
        pb.redirectErrorStream();
        BufferedReader reader = null;
        try{
            Process p = pb.start();
            InputStream inputStream = p.getInputStream();
            BufferedReader error = new BufferedReader(new InputStreamReader(p.getErrorStream()));
            reader = new BufferedReader(new InputStreamReader(inputStream));
            p.waitFor(60, TimeUnit.SECONDS);
            String line;
            while((line = error.readLine()) != null)
            {
                System.out.println(line);
            }
//System.out.println("Import Complete");
        }
        catch (Exception e){
            System.out.println(e);
            System.out.println("Import Failed. Ensure you have entered the proper credentials and IP address. ");
        }
        return reader;
    }
    /**
     * Attempt to parse the SEL entries against the lookup table. 
     *  
     * @param selList The buffered reader object that contains the SEL entries
     * @return The number of events parsed
     */
    private static int processSels(BufferedReader selList){
        String line;
        int alertCount = 0;
        try{
            while((line = selList.readLine()) != null){
                BmcEventParser bmcPars = new BmcEventParser();
                BmcEvent cerEvent;
                String[] selPieces = formatSEL(line);
                cerEvent = bmcPars.getEventNode(selPieces[BmcEvent.SENSOR_LOC], selPieces[BmcEvent.STATE_LOC], selPieces[BmcEvent.DETAILS_LOC]);
                System.out.println(cerEvent);
                alertCount++;
            }
            //System.out.println("Processed " + String.valueOf(alertCount) + " alerts.");
        }
        catch(Exception e){
            System.out.println(e);
        }
        return alertCount;
    }
    /**
     * Attempt to parse the SEL entries against the lookup table. 
     *  
     * @param selList The buffered reader object that contains the SEL entries
     * @return The number of events parsed
     */
    private static int processSelsHashMap(BufferedReader selList){
        String line;
        int alertCount = 0;
        BmcEventParser bmcPars = new BmcEventParser();
        Map<String,Map> lookupEvents;
        //load xml into hashMap
        
        try{
            long processTimeStart = System.currentTimeMillis();
            lookupEvents = bmcPars.fromNodeList(bmcPars.getEventNodes());
            long processTimeEnd = System.currentTimeMillis();
            //System.out.println("Time to create hash map from xml: "+ String.valueOf(processTimeEnd-processTimeStart) + " ms");
            processTimeStart = System.currentTimeMillis();
            System.out.println("{");
            while((line = selList.readLine()) != null){
                
                BmcEvent cerEvent;
                String[] selPieces = formatSEL(line);
                String dateTime = selPieces[BmcEvent.DATE_LOC].trim() +" " + selPieces[BmcEvent.TIME_LOC].trim();
                DateFormat df = new SimpleDateFormat("MM/dd/yyyy HH:mm:ss");
                Date parsedTS = df.parse(dateTime);
                String unixTimestamp = Long.toString(parsedTS.getTime()/1000);
                String mapKey = getMapKey(selPieces, lookupEvents);
                Map eventAttr = null;
                eventAttr = (lookupEvents.get(mapKey));
                if (eventAttr != null){
                    cerEvent = createCEREventFromMap(eventAttr);
                    cerEvent.setTimestamp(unixTimestamp);
                    //System.out.println(cerEvent.getSensor() + cerEvent.getState());
                    System.out.println("\t\"event" + alertCount+ "\":" + cerEvent.toJSON() + ",");
                }
                else{
                    System.out.println("\t\"event"+ alertCount+ "\":" + "{\n\t\"error\": \"Could not find: " + mapKey+ "\" \n},");
                }
                alertCount++;
            }
            System.out.println("\t\"numAlerts\": "+ alertCount);
            System.out.println("}");
            processTimeEnd = System.currentTimeMillis();
            //System.out.println("Processed " + String.valueOf(alertCount) + " alerts.");
            if(alertCount>0){
                //System.out.println("Time Processing Alerts: " + String.valueOf(processTimeEnd - processTimeStart) + " ms");
                //System.out.println("Average time per alert: " + String.valueOf((processTimeEnd - processTimeStart)/alertCount) + " ms.");
            }
            
        }
        catch(Exception e){
            System.out.println(e);
        }
        return alertCount;
    }
    private static BmcEvent createCEREventFromMap(Map eventMap){
        BmcEvent newEvent = new BmcEvent();
        newEvent.setCerId(eventMap.get("CommonEventID").toString());
        newEvent.setSensor(eventMap.get("Sensor").toString());
        newEvent.setState(eventMap.get("State").toString());
        newEvent.setAddDetails(eventMap.get("AdditionalDetails").toString());
        newEvent.setMessage(eventMap.get("Message").toString());
        if(eventMap.get("Serviceable").toString().equals("Yes")){
            newEvent.setServiceable(true);
        }
        else{
            newEvent.setServiceable(false);
        }
        if(eventMap.get("CallHomeCandidate").toString().equals("Yes")){
            newEvent.setCallHome(true);
        }
        else{
            newEvent.setCallHome(false);
        }
        newEvent.setSeverity(eventMap.get("Severity").toString());
        newEvent.setEventType(eventMap.get("EventType").toString());
        newEvent.setVmMigration(eventMap.get("VMMigrationFlag").toString());
        newEvent.setSubSystem(eventMap.get("AffectedSubsystem").toString());
        newEvent.setUserAction(eventMap.get("UserAction").toString());
        return newEvent;
    }
    /**
     * Format the SEL entry so it can properly be parsed. Breaks the entry into multiple strings that contain the various components of a SEL. 
     *  
     * @param selEntry A single SEL entry to be formatted
     * @return A String array containing the formatted pieces of the SEL entry. 
     */
    private static String[] formatSEL(String selEntry){
        String[] formattedSEL = selEntry.split("\\|");
        formattedSEL[BmcEvent.STATE_LOC] = formattedSEL[BmcEvent.STATE_LOC].replace("()", "");
        //Arrays.parallelSetAll(formattedSEL, i -> formattedSEL[i].trim());
        formattedSEL[BmcEvent.SENSOR_LOC] = formattedSEL[BmcEvent.SENSOR_LOC].trim().toLowerCase();
        formattedSEL[BmcEvent.STATE_LOC] = formattedSEL[BmcEvent.STATE_LOC].trim().toLowerCase();
        if(!formattedSEL[BmcEvent.SENSOR_LOC].equals("oem record df")){
            formattedSEL[BmcEvent.DETAILS_LOC] = formattedSEL[BmcEvent.DETAILS_LOC].trim().toLowerCase();
        }
        
        
        // map sel list result (3,4,5) from description to eventID
        // need to massage the state string, since parenthesis values are not matched but still need to be kept.
        int openPar = formattedSEL[BmcEvent.STATE_LOC].indexOf('(');
        String innerParString="";
        if ( openPar > -1 ){
            innerParString = formattedSEL[BmcEvent.STATE_LOC].substring(openPar);
            formattedSEL[BmcEvent.STATE_LOC] = formattedSEL[BmcEvent.STATE_LOC].substring(0,openPar).trim();
            //LOGGER.info("device found in state field: "+innerParString);
        }
        return formattedSEL;
    }
    /**
     * Generate the Key for looking up alerts from the hash map lookup table. This takes into account regex keys for OEM record ipmi events. 
     *  
     * @param selPieces The original sel entry split into pieces so that each field is accessible
     * @param lookupEvents The hash map containing the lookup table
     * @return A String to be used as the key for lookup events 
     */
    private static String getMapKey(String selPieces[], Map<String,Map> lookupEvents){
        String newMapKey = null;
        switch (selPieces[BmcEvent.SENSOR_LOC]){
            case "oem record df":
                newMapKey = "oem record df|.*|.*";
                break;
            case "oem record de":
                for(String key : lookupEvents.keySet()){
                    if(key.startsWith("oem record de|040020")){
                        String[] splitKey = key.split("\\|");
                        String regex = splitKey[2];
                        Pattern p = Pattern.compile(regex);
                        Matcher m = p.matcher(selPieces[BmcEvent.DETAILS_LOC]);
                        if(m.matches()){
                            newMapKey = key;
                            break;
                        }
                    }
                    else if(key.startsWith("oem record de")){
                        newMapKey = "oem record de|.*|.*";
                        break;
                    }
                }
                if(newMapKey.equals(null)){
                    newMapKey = "oem record de|.*|.*";
                }
                break;
            case "oem record c0":
                for(String key : lookupEvents.keySet()){
                    if(key.startsWith("oem record c0")){
                        String[] splitKey = key.split("\\|");
                        String regex = splitKey[2];
                        Pattern p = Pattern.compile(regex);
                        Matcher m = p.matcher(selPieces[BmcEvent.DETAILS_LOC]);
                        if(m.matches()){
                            newMapKey = key;
                            break;
                        }
                    }
                }
                if(newMapKey.equals(null)){
                    newMapKey = "oem record c0|.*|.*";
                }
                break;
            default:
                newMapKey = selPieces[BmcEvent.SENSOR_LOC]+ "|"+ selPieces[BmcEvent.STATE_LOC]+"|"+ selPieces[BmcEvent.DETAILS_LOC];
        
        }
        return newMapKey;
    }
}
