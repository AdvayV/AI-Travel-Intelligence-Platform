import logging
from vector.chroma_client import ChromaClient

logger = logging.getLogger(__name__)

def load_documents():
    chroma = ChromaClient()
    
    # ------------------ 1. Seeding fare_rules collection ------------------
    fare_rules_col = chroma.get_or_create_collection("fare_rules")
    if fare_rules_col.count() == 0:
        logger.info("Seeding Chroma collection 'fare_rules'...")
        
        fare_docs = [
            # Fare Y
            ("Full Economy Fare Class Y rules and regulations. This class represents fully flexible economy travel. "
             "Under IATA Tariff Rule Y-101, change fees are standard at INR 8,000 per sector per transaction, subject to seat availability in the same class. "
             "Cancellations made up to 24 hours prior to departure are eligible for a 75% refund of the base fare. "
             "Upgrade paths are permitted to J (Full Business) or C (Semi-restricted Business) by paying the fare difference plus a processing charge. "
             "Blackout dates do not apply to Y class, making it ideal for standard business bookings. "
             "Group bookings are not eligible for Y class discounts. There is no minimum stay requirement, "
             "and ticket validity extends to 365 days from the date of issue. Complimentary check-in baggage allowance is 30kg, "
             "and premium seat selection is included free of charge."),
             
            # Fare M
            ("Semi-restricted Economy Fare Class M guidelines. M class represents a mid-tier, semi-flexible economy fare product. "
             "Changes to routing or date are permitted up to 48 hours prior to scheduled departure for a fee of INR 5,000 per passenger, "
             "plus any applicable fare difference. Cancellation of tickets issued in M class qualifies for a 50% refund of the base fare "
             "provided the request is logged in the GDS no later than 72 hours before flight time; within 72 hours, the fare becomes completely non-refundable. "
             "Upgrades to business class are permitted using corporate loyalty miles or by paying the standard commercial upgrade fee at the gate. "
             "Blackout dates may apply during peak seasonal windows, specifically during December holidays and summer vacation periods. "
             "Minimum stay of 3 days or a Sunday rule is required. Standard baggage allowance is 20kg."),
             
            # Fare K
            ("Restricted Economy Fare Class K restrictions. K class is a discount economy fare designed for price-sensitive corporate travelers. "
             "Ticket changes are allowed up to 7 days before departure for a modification fee of INR 3,000 plus fare difference. "
             "Cancellations in K class are strictly non-refundable; no cash refund or travel credit will be issued under any circumstances. "
             "Upgrades are restricted and can only be requested at the time of check-in, subject to space availability and double upgrade fees. "
             "Frequent flyer miles accumulation is capped at 50% of actual miles flown. Blackout dates are strictly enforced on this fare family, "
             "covering major national holidays, festival seasons, and peak corporate travel weeks. "
             "No group bookings or routing changes are allowed. Baggage allowance is strictly limited to 1 piece up to 15kg."),
             
            # Fare Q
            ("Deep Discount Economy Fare Class Q operational constraints. Q class is a promotional deep-discount fare. "
             "It is strictly non-changeable and non-refundable. Any modification to date, flight, or route requires the passenger to forfeit the ticket "
             "and purchase a new fare. No refunds, taxes included, will be processed upon non-show. "
             "Upgrade paths are completely blocked; passengers cannot upgrade to Business class even with cash or miles. "
             "No frequent flyer miles are earned on Q class bookings. Priority boarding is unavailable, and seat selection is auto-assigned at check-in. "
             "Baggage is restricted to hand luggage only (max 7kg); checked baggage must be purchased separately. "
             "This fare class is excluded from all corporate policy agreements and cannot be used for business travel compliance."),
             
            # Fare J
            ("Full Business Fare Class J rules. J class is the highest premium business class product. "
             "It offers maximum flexibility with zero change fees for any modification made prior to flight departure. "
             "Cancellations are 100% refundable with no penalties. Upgrades to First Class are fully supported and prioritized on routes operated by widebody aircraft. "
             "No blackout dates apply, guaranteeing seat availability up to 2 hours before departure. "
             "Includes access to corporate premium lounges, fast-track security clearance, priority boarding, and a generous baggage allowance of 40kg. "
             "Miles are earned at a rate of 200%. Suitable for executive-level travel where itinerary changes are frequent and unpredictable. "
             "No minimum stay required, and open jaw tickets are fully supported."),
             
            # Fare C
            ("Semi-restricted Business Fare Class C guidelines. C class is a flexible business product with minor restrictions. "
             "Ticket modifications are permitted up to 12 hours before flight departure for a flat fee of INR 15,000 plus fare difference. "
             "Cancellations are refundable, with an 80% refund of the base fare and full refund of passenger taxes. "
             "Upgrades using miles are allowed but rank lower in priority compared to J class. "
             "Blackout dates may apply during international summit weeks and peak holiday seasons. "
             "Baggage allowance is 35kg. Lounge access is complimentary. Recommended for senior management travel where dates are mostly stable but minor adjustments may occur. "
             "Frequent flyer miles are credited at 150% of distance flown."),
             
            # Fare D
            ("Discounted Business Fare Class D terms. D class is a promotional business class fare. "
             "Date modifications are permitted up to 72 hours before departure for a fee of INR 25,000. "
             "The ticket is completely non-refundable; cancellations will result in the loss of the entire base fare, though unused airport taxes can be refunded. "
             "Upgrades to higher cabins are not permitted. Blackout dates are active during peak holiday travel periods. "
             "Lounge access is included, and baggage allowance is restricted to 30kg. "
             "Miles accumulation is set at 100%. This class is subject to seat allocation limits and is typically unavailable for last-minute bookings. "
             "Minimum stay of 7 days is required for international sectors."),
             
            # Fare G
            ("Group Fare Class G contract rules. G class is dedicated to group bookings of 10 or more passengers traveling together on the same itinerary. "
             "Changes to the group size or names can be made up to 14 days before departure for a fee of INR 10,000 per name change. "
             "Cancellations of the entire group booking are permitted up to 30 days before departure for a 25% refund; "
             "otherwise, the booking is non-refundable. Upgrade paths are not permitted. "
             "Blackout dates apply during peak student travel seasons and national holidays. "
             "Baggage allowance is pooled at 20kg per passenger. Group check-in is required at the airport counter. "
             "Special meal requests must be submitted at least 72 hours in advance. Ticket validity is restricted to the specific booked flights only.")
        ]
        
        fare_ids = [f"RULE_{fc}" for fc in ["Y", "M", "K", "Q", "J", "C", "D", "G"]]
        fare_metas = [{"fare_class": fc, "type": "fare_rule"} for fc in ["Y", "M", "K", "Q", "J", "C", "D", "G"]]
        
        chroma.add_documents("fare_rules", fare_docs, fare_ids, fare_metas)
        
    # ------------------ 2. Seeding corporate_policies collection ------------------
    corp_policies_col = chroma.get_or_create_collection("corporate_policies")
    
    import os
    import zipfile
    import xml.etree.ElementTree as ET
    
    docx_path = "../../enhanced_synthetic_company_travel_policy_25_pages.docx"
    if not os.path.exists(docx_path):
        docx_path = "../enhanced_synthetic_company_travel_policy_25_pages.docx"
    if not os.path.exists(docx_path):
        docx_path = "enhanced_synthetic_company_travel_policy_25_pages.docx"

        
    if os.path.exists(docx_path):
        logger.info(f"Seeding corporate_policies from custom company guidelines: {docx_path}")
        try:
            paragraphs = []
            with zipfile.ZipFile(docx_path) as z:
                xml_content = z.read('word/document.xml')
                root = ET.fromstring(xml_content)
                namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                for p in root.findall('.//w:p', namespaces):
                    text_elems = p.findall('.//w:t', namespaces)
                    text = "".join([t.text for t in text_elems if t.text])
                    if text.strip():
                        paragraphs.append(text.strip())
            
            # Chunk the paragraphs
            chunks = []
            current_chunk = []
            current_len = 0
            for p in paragraphs:
                current_chunk.append(p)
                current_len += len(p)
                if current_len > 1500:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_len = 0
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                
            logger.info(f"Extracted {len(chunks)} document chunks from travel policy docx.")
            
            # Reset collection and seed docx chunks
            chroma.delete_collection("corporate_policies")
            corp_policies_col = chroma.get_or_create_collection("corporate_policies")
            
            policy_ids = [f"POLICY_DOCX_{i}" for i in range(len(chunks))]
            policy_metas = [{"policy_id": "CP-ALL", "type": "docx_policy", "chunk_index": i} for i in range(len(chunks))]
            
            chroma.add_documents("corporate_policies", chunks, policy_ids, policy_metas)
            logger.info("Successfully loaded and indexed DOCX company guidelines into ChromaDB!")
            
        except Exception as e:
            logger.error(f"Failed to seed corporate policies from docx: {e}. Falling back to default policies.")
            _seed_default_policies(chroma, corp_policies_col)
    else:
        logger.info("Guidelines DOCX not found. Seeding default corporate policies.")
        _seed_default_policies(chroma, corp_policies_col)

    # ------------------ 3. Seeding irops_history collection ------------------
    irops_history_col = chroma.get_or_create_collection("irops_history")
    if irops_history_col.count() == 0:
        logger.info("Seeding Chroma collection 'irops_history'...")
        
        irops_docs = [
            # Event 1: BOM Monsoon
            ("IROPS Incident Report: BOM Monsoon Delays. Date: July 14, 2025. Affected Route: BOM-DXB, BOM-SIN. "
             "Heavy precipitation exceeding 350mm in 24 hours caused severe flooding on the runways of Mumbai Chhatrapati Shivaji Maharaj Airport (BOM). "
             "A total of 42 flights were delayed, and 12 were diverted. "
             "Waiver WX-2025-MONSOON was activated, allowing change fees to be waived. "
             "Passenger count affected: 1,800 corporate travelers. Resolution time: 36 hours. "
             "Lessons learned: Airlines must position backup aircraft in DEL to bypass flooded runway constraints; "
             "passengers should be proactively re-routed through BLR or HYD hubs."),
             
            # Event 2: DEL Fog
            ("IROPS Incident Report: Delhi Fog Operations. Date: January 18, 2025. Affected Route: DEL-JFK, DEL-LHR. "
             "Dense fog conditions reduced runway visual range (RVR) to less than 50 meters, halting all non-CAT-III compliance flights. "
             "Over 150 flights were delayed, and 30 cancelled at Delhi Indira Gandhi International (DEL). "
             "Waiver DEL-FOG-JAN25 was issued. "
             "Passenger count affected: 3,500 travelers. Resolution time: 48 hours. "
             "Lessons learned: Corporate clients must be booked on CAT-III certified aircraft (Boeing 777 or Airbus A350) "
             "and pilots during winter months to ensure departure capability. Re-routing via BOM is recommended."),
             
            # Event 3: DXB Sandstorm
            ("IROPS Incident Report: Dubai Sandstorm Diversion. Date: April 02, 2026. Affected Route: BOM-DXB, HYD-DXB. "
             "Severe sandstorms with wind gusts up to 65 knots reduced visibility at Dubai International (DXB), leading to airspace closure. "
             "8 flights from India were diverted to Muscat (MCT) and Doha (DOH). "
             "Waiver DXB-SAND-2026 was activated. "
             "Passenger count affected: 1,200 passengers. Resolution time: 14 hours. "
             "Lessons learned: Maintain agreements with hotels in Doha and Muscat for corporate travelers. "
             "Ensure GDS profiles contain current mobile numbers to trigger SMS notifications regarding diversions."),
             
            # Event 4: LHR Strike
            ("IROPS Incident Report: Heathrow Industrial Action. Date: September 12, 2025. Affected Route: BOM-LHR, DEL-LHR. "
             "Wildcat strike action by Heathrow Airport baggage handlers and security staff led to 40% reduction in operating slots. "
             "British Airways and Air India cancelled 15 flights to/from India. "
             "Waiver LHR-STRIKE-SEP25 was activated. "
             "Passenger count affected: 2,100 travelers. Resolution time: 72 hours. "
             "Lessons learned: Standard policy should authorize immediate rerouting on Middle East carriers (EK or QR) "
             "via DXB/DOH to bypass LHR delays. Corporate travelers should travel with hand luggage only during strike warnings."),
             
            # Event 5: SIN Typhoon
            ("IROPS Incident Report: Singapore Typhoon Backup. Date: November 05, 2025. Affected Route: MAA-SIN, BLR-SIN. "
             "Typhoon signal number 4 in the South China Sea caused flight paths to Singapore Changi (SIN) to be restructured, "
             "leading to average delays of 3.5 hours for incoming flights. "
             "Waiver SIN-TYPH-2025 was active. "
             "Passenger count affected: 850 travelers. Resolution: Flights were routed via Kuala Lumpur (KUL). "
             "Lessons learned: Airlines must establish alternate routing coordinates through Malaysian airspace. "
             "Corporate travelers should schedule buffer times of at least 6 hours for connecting flights in SIN during November."),
             
            # Event 6: BOM Cyclone
            ("IROPS Incident Report: Cyclone Phyan Routing. Date: November 11, 2024. Affected Route: BOM-BKK, BOM-SIN. "
             "Cyclone Phyan generated storm surges and high winds in the Arabian Sea, affecting Mumbai departures. "
             "18 flights cancelled, and 4 diverted. "
             "Waiver CYCLONE-PHYAN-24 was activated by Air India. "
             "Passenger count affected: 950 corporate travelers. Resolution time: 24 hours. "
             "Lessons learned: Early storm tracking allowed 60% of travelers to reschedule 24 hours prior to the storm hitting. "
             "GDS automated re-accommodation script saved 4 hours of manual processing time per PNR."),
             
            # Event 7: DXB Flooding
            ("IROPS Incident Report: Dubai Heavy Rainfall Flooding. Date: April 16, 2024. Affected Route: DEL-DXB, HYD-DXB. "
             "Record rainfall in the UAE caused severe flooding on access roads to DXB, preventing cabin crew and passengers from reaching terminals. "
             "Flights were suspended for 24 hours. "
             "Waiver DXB-RAIN-24 was issued. "
             "Passenger count affected: 4,000 travelers. Resolution time: 5 days. "
             "Lessons learned: Transport infrastructure failure requires booking passengers in airport-adjacent hotels "
             "that do not require highway access. Enable immediate remote ticket re-issuance without physical GDS queueing."),
             
            # Event 8: DEL Air Quality
            ("IROPS Incident Report: Delhi Air Quality/Smog Delays. Date: November 22, 2025. Affected Route: DEL-CDG, DEL-SIN. "
             "Seasonal crop burning combined with low winds created a thick smog layer, reducing visibility to 200 meters during morning hours. "
             "35 departures were delayed by 2-4 hours. "
             "Waiver DEL-SMOG-NOV25 was activated. "
             "Passenger count affected: 1,500 travelers. Resolution: Departures shifted to afternoon slots. "
             "Lessons learned: Reschedule high-priority corporate departures during November to afternoon/evening slots (after 13:00) "
             "to avoid predictable morning smog delays."),
             
            # Event 9: LHR ATC Failure
            ("IROPS Incident Report: Heathrow Air Traffic Control Outage. Date: August 28, 2025. Affected Route: BOM-LHR. "
             "A technical glitch in the UK NATS system prevented the processing of flight plans automatically, forcing manual entry. "
             "Capacities were restricted by 80% across the UK airspace. "
             "Waiver UK-NATS-ATC was activated. "
             "Passenger count affected: 1,100 travelers. Resolution time: 30 hours. "
             "Lessons learned: Implement immediate fallback to train routing (Eurostar) via CDG or AMS "
             "for corporate passengers stranded in mainland Europe trying to reach London Heathrow."),
             
            # Event 10: CDG Baggage Failure
            ("IROPS Incident Report: Paris CDG Baggage Sorting System Failure. Date: June 15, 2025. Affected Route: DEL-CDG. "
             "A major electrical fault in Terminal 2E baggage sorting computer halted automated processing, "
             "resulting in thousands of bags missing connecting flights. "
             "No official airline waiver was issued, but corporate travel agents logged service requests for baggage delivery. "
             "Passenger count affected: 600 passengers. Resolution time: 7 days. "
             "Lessons learned: Recommend passengers carry high-value sales materials and clean clothing in carry-on baggage. "
             "Implement automatic baggage tracking codes in the corporate client dashboard.")
        ]
        
        irops_ids = [f"IROPS_{i}" for i in range(1, 11)]
        irops_metas = [{"incident_id": f"INC-{i:03d}", "type": "irops_narrative"} for i in range(1, 11)]
        
        chroma.add_documents("irops_history", irops_docs, irops_ids, irops_metas)
        
    logger.info("Chroma vector databases fully seeded and ready")


def _seed_default_policies(chroma, corp_policies_col):
    logger.info("Seeding comprehensive default corporate travel policies into ChromaDB...")
    default_docs = [
        # CP-001: Class Guidelines
        ("Corporate Travel Policy Clause CP-001 - Air Cabins & Classes: "
         "All standard employees (non-executive grades) must book Economy Class (specifically restricted to Fare Classes Y, M, K, Q) "
         "for all flights under 6 hours block time. Business Class travel (Fare Classes J, C, D) is permitted only for "
         "senior management (VPs and above) or when the flight duration exceeds 6 hours of continuous travel (e.g. BOM to JFK or DEL to LHR). "
         "Deep discount economy class Q is allowed but offers restricted baggage rules. First Class travel requires CEO approval."),
        
        # CP-002: Advance Booking
        ("Corporate Travel Policy Clause CP-002 - Booking Window & Lead Times: "
         "All business travel bookings must be confirmed at least 14 days prior to departure to secure optimal corporate tariffs. "
         "Bookings completed between 7 to 13 days in advance require Department Head notification. Last-minute bookings completed "
         "within 7 days of departure require written justification of business urgency, are subject to Department Head approval, "
         "and trigger automated policy compliance audits."),
        
        # CP-003: Hotel Night Caps
        ("Corporate Travel Policy Clause CP-003 - Lodging & Accommodation Caps: "
         "Corporate hotel bookings must utilize preferred corporate lodging partners. Maximum allowable nightly room rates "
         "are capped at INR 10,000 for Tier-1 cities (Mumbai, Delhi, Bengaluru, London, New York) and INR 6,000 for Tier-2 cities. "
         "Any accommodation rate exceeding these thresholds must be routed through the Corporate Travel Desk for exception approvals."),
        
        # CP-004: Weather & Disruption Deviations
        ("Corporate Travel Policy Clause CP-004 - Monsoon & Severe Weather Disruption Exceptions: "
         "In the event of severe weather warnings (such as the annual Indian Monsoon in Mumbai/BOM or winter smog in Delhi/DEL), "
         "travelers departing from affected airports are granted automatic exemptions from advance booking windows. "
         "When an active airline waiver (e.g., WX-2026-INDIA) is declared, the booking lead time requirement is reduced to 2 days, "
         "and upgrades to full economy (Class Y) are authorized to ensure business continuity without penalty fees."),
        
        # CP-005: Expense Limits & Approval Thresholds
        ("Corporate Travel Policy Clause CP-005 - Expense Authorization & Limits: "
         "Domestic travel expense claims are capped at INR 8,000 per day covering meals and local taxi fares. International daily allowance "
         "is capped at USD 150. Any single transaction exceeding INR 100,000 (excluding standard economy flight tickets) requires "
         "explicit Department Head pre-approval before corporate credit cards are charged."),
        
        # CP-006: Booking Channels
        ("Corporate Travel Policy Clause CP-006 - Authorized Booking Channels: "
         "All corporate travel (flights, hotels, car rentals) must be booked exclusively through the corporate GDS tool "
         "or authorized corporate travel agents. Direct bookings on public consumer travel sites are strictly non-reimbursable "
         "unless the booking was made under emergency circumstances during GDS system down-times."),
        
        # CP-007: Preferred Carriers & Discounts
        ("Corporate Travel Policy Clause CP-007 - Preferred Airline Partner Programs: "
         "Travelers should prioritize booking flights with preferred airline partners (including Air India / AI and IndiGo / 6E). "
         "Air India flights booked under corporate GDS agreements qualify for a 12% corporate discount using waiver contract code CORP-AI-ANNUAL. "
         "Bookings on non-preferred airlines are permitted only if preferred carrier flights are unavailable or cost 20% more."),
        
        # CP-008: Ticket Cancellations & Changes
        ("Corporate Travel Policy Clause CP-008 - Ticket Cancellations & Itinerary Changes: "
         "Flight changes must be completed in the GDS at least 24 hours prior to departure. Non-refundable promotional fare classes (such as Q) "
         "must not be changed unless approved by the Business Unit Head. Involuntary changes due to airline schedule adjustments or active waivers "
         "are exempt from GDS change fee processing charges."),
        
        # CP-009: Group Travel Bookings
        ("Corporate Travel Policy Clause CP-009 - Group Travel & Event Logistics: "
         "Bookings containing 10 or more employees traveling on the same flight or to the same destination must be managed under group contracts (Fare Class G). "
         "To minimize corporate risk, no more than 15 employees from the same department may travel on the same aircraft sector."),
         
        # CP-010: Emergency Evacuation & Assistance
        ("Corporate Travel Policy Clause CP-010 - Duty of Care & Emergency Assistance: "
         "During active emergencies, natural disasters, or major air traffic failures, the Corporate Travel Desk is authorized "
         "to auto-rebook travelers on weather-resilient alternative routes (such as re-routing Mumbai departures through the BLR hub). "
         "Emergency hotel rates up to 150% of the standard cap are pre-authorized for stranded travelers.")
    ]
    ids = [f"DEFAULT_POLICY_{i}" for i in range(len(default_docs))]
    metas = [{"policy_id": f"CP-{i+1:03d}", "type": "default_policy"} for i in range(len(default_docs))]
    chroma.add_documents("corporate_policies", default_docs, ids, metas)


