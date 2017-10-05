package ipmiSelParser;

import java.io.File;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.xpath.XPath;
import javax.xml.xpath.XPathConstants;
import javax.xml.xpath.XPathExpression;
import javax.xml.xpath.XPathExpressionException;
import javax.xml.xpath.XPathFactory;

import org.w3c.dom.Document;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

//import com.ibm.sfp.SfpResource;
//import com.ibm.sfp.p.service.utils.SFPCommonLogger;
//import com.ibm.sfp.p.service.utils.SFPProperties;

/**
 * Event Parser class for BMC events. This is used to match an event from the ipmitool's sel list command to the 
 * respective CerId from the BMC's lookup xml.
 */
public class BmcEventParser{
    //private static final Logger LOGGER = SFPCommonLogger.getLogger(SFPProperties.BMCLOGGER);
    
    //private static final String EVENTSPATH = SfpResource.getBmcPath() + File.separator + "bmc-events.xml";
    //private static final String EVENTSPATH = System.getProperty("user.dir") +File.separator + "bmc-events.xml";
    //need to update previous line to allow a selection between multiple files based on mt
    private static final String EVENTSPATH = File.separator + "ipmiSelParser" + File.separator +"resources" + File.separator + "p9SMCBMCevents.xml";
    
    // Query variables
    private static final String XP_CLEAR_WHITESPACE = "//text()[normalize-space(.) = '']";
    private static final String XP_SENSOR_LOWER = "//Event[Sensor[translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')=\"";
    private static final String XP_STATE_LOWER = "\"] and State[translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')=\"";
    private static final String XP_DETAILS_LOWER = "\"] and AdditionalDetails[translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')=\"";
    
    private static final String XP_ID = "./@ID";
    private static final String XP_TYPE = "./EventType";
    private static final String XP_MESSAGE = "./Message";
    private static final String XP_SENSOR = "./Sensor";
    private static final String XP_SERVICEABLE = "./Serviceable";
    private static final String XP_SEVERITY = "./Severity";
    private static final String XP_STATE = "./State";
    private static final String XP_SUBSYSTEM = "./AffectedSubsystem";
    private static final String XP_VMMIGRATION = "./VMMigrationFlag";
    private static final String XP_USERACTION = "./UserAction";
    private static final String XP_ADDITIONAL_DETAILS = "./AdditionalDetails";
    private static final String XP_CALLHOME = "./CallHomeCandidate";
    
    
    private static Document doc;
    private static XPath xpath;
    
    /**
     * Construct a parser instance. EVENTSPATH will be /opt/sfp/data/service/bmc .
     * Whitespace will be removed for parsing simplicity
     */
    public BmcEventParser(){
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        DocumentBuilder builder;
        try {
            builder = factory.newDocumentBuilder();
            InputStream is = getClass().getResourceAsStream(EVENTSPATH);
            doc = builder.parse(is);
            
            XPathFactory xPathFactory = XPathFactory.newInstance();
            xpath = xPathFactory.newXPath();
            
            //remove whitespace
            XPathExpression xpathExp = xpath.compile(XP_CLEAR_WHITESPACE);  
            NodeList emptyTextNodes = (NodeList) 
                    xpathExp.evaluate(doc, XPathConstants.NODESET);
            // Remove each empty text node from document.
            for (int i = 0; i < emptyTextNodes.getLength(); i++) {
                Node emptyTextNode = emptyTextNodes.item(i);
                emptyTextNode.getParentNode().removeChild(emptyTextNode);
            }
        } catch (Exception e) {
            System.out.println(e);
        }
    }
    
    /**
     * Attempt to match an event from the BMC's lookup xml using the sensor, state, and addition detail fields from
     * the sel list command results.
     *  
     * @param sensor
     * @param state The state parameter expects the specific device to have been removed, since the xml expects generic fields.
     * @param details
     * @return
     */
    
    public BmcEvent getEventNode(String sensor, String state, String details){
        String query = XP_SENSOR_LOWER+sensor.toLowerCase() + XP_STATE_LOWER+state.toLowerCase() + XP_DETAILS_LOWER+details.toLowerCase()+"\"]]";
        //String eventNodeString="";
        BmcEvent event = null;
        
        //LOGGER.info("compiling on: "+query);
        XPathExpression expr;
        try {
            expr = xpath.compile(query);
        
            Node eventNode = (Node) expr.evaluate(doc,XPathConstants.NODE);
        
            if (eventNode != null){
                NodeList childrenList = eventNode.getChildNodes();
                for ( int i=0 ; i < childrenList.getLength() ; i++){
                    Node n = childrenList.item(i);
                    //eventNodeString += n.getNodeName()+": "+n.getTextContent()+"\n";
                }
                //LOGGER.info("completeString: "+eventNodeString);
                
                event = parseFromNode(eventNode);
            }
        } catch (XPathExpressionException e) {
            //LOGGER.log(Level.SEVERE, "exception caught while reading xml: ",e);
            System.out.println(e);
        }
        
        return event;
    }
    
    /**
     * Use a Node from the BMC's lookup xml to create the {@link BmcEvent} to be returned.
     * @param node Dom node that contains the xml information to be parsed.
     * @return {@link BmcEvent} with values matched to existing fields from the xml
     * @throws XPathExpressionException
     */
    public static BmcEvent parseFromNode(Node node) throws XPathExpressionException{
        BmcEvent event = new BmcEvent();
        event.setAddDetails((String) xpath.evaluate(XP_ADDITIONAL_DETAILS, node, XPathConstants.STRING));
        if ( "Yes".equals( (String)(xpath.evaluate(XP_CALLHOME, node, XPathConstants.STRING)) ) ){
            event.setCallHome(true);
        } else {
            event.setCallHome(false);
        }
        event.setCerId((String) xpath.evaluate(XP_ID, node, XPathConstants.STRING));
        event.setEventType((String) xpath.evaluate(XP_TYPE, node, XPathConstants.STRING));
        event.setMessage((String) xpath.evaluate(XP_MESSAGE, node, XPathConstants.STRING));
        event.setSensor((String) xpath.evaluate(XP_SENSOR, node, XPathConstants.STRING));
        if ( "Yes".equals( xpath.evaluate(XP_SERVICEABLE, node, XPathConstants.STRING) ) ){
            event.setServiceable(true);
        } else {
            event.setServiceable(false);
        }
        event.setSeverity((String) xpath.evaluate(XP_SEVERITY, node, XPathConstants.STRING));
        event.setState((String) xpath.evaluate(XP_STATE, node, XPathConstants.STRING));
        event.setSubSystem((String) xpath.evaluate(XP_SUBSYSTEM, node, XPathConstants.STRING));
        event.setVmMigration((String) xpath.evaluate(XP_VMMIGRATION, node, XPathConstants.STRING));
        event.setUserAction((String) xpath.evaluate(XP_USERACTION, node, XPathConstants.STRING));
        
        return event;
    }
    
    /**
     * Gets a list of all the Event nodes from the xml document and returns a NodeList
     * @return {@link NodeList} with all of the event nodes in the Lookup Table for processing
     * @throws XPathExpressionException
     */
    public NodeList getEventNodes() throws XPathExpressionException  {
        final XPath xpath = XPathFactory.newInstance().newXPath();
        final XPathExpression expr = xpath.compile("/Event_Documentation/Events/Event");
        return (NodeList) expr.evaluate(this.doc, XPathConstants.NODESET);
    }
    /**
     * Get a list of all events and their attributes
     * @param node Dom node that contains the xml information to be parsed.
     * @return {@link BmcEvent} with values matched to existing fields from the xml
     * @throws XPathExpressionException
     */
    public Map<String, Map> fromNodeList(final NodeList nodes) {
        //final List<Map<String, List>> eventList = new ArrayList<Map<String,List>>();
        Map<String, Map> lookupValue = new HashMap<String, Map>();
        int len = (nodes != null) ? nodes.getLength() : 0;
        //go through each event
        for (int i = 0; i < len; i++) {
            NodeList eventAttributes = nodes.item(i).getChildNodes();
            String sensor, state, additionalDetails, attrName;
            sensor = "";
            state = "";
            additionalDetails = "";
            Map<String, String> attr = new HashMap<String, String>();
            //get the event attributes
            for (int j = 0; j < eventAttributes.getLength(); j++) {
                Node child = eventAttributes.item(j);
                if (child.getNodeType() == Node.ELEMENT_NODE){
                    attrName = child.getNodeName();
                    attr.put(attrName, child.getTextContent());
                    switch (attrName) {
                        case "Sensor":
                            sensor = child.getTextContent();
                        case "State":
                            state = child.getTextContent();
                        case "AdditionalDetails":
                            additionalDetails = child.getTextContent();
                    }
                }
            }
            lookupValue.put(sensor.trim().toLowerCase() + "|" + state.trim().toLowerCase() + "|" + additionalDetails.trim().toLowerCase(), attr);
            //eventList.add(lookupValue);
        }
        return lookupValue;
    } 
}