# ingest_formats.py — run this ONCE to feed all enquiry texts into ChromaDB[cite: 1]
# This is not part of the web server, just a standalone script[cite: 1]

import json
from embeddings import model, format_collection

# Step 1: Define all enquiries with code, topic and text[cite: 1]
# This is structured from the Freehold Title Check Enquiries document[cite: 1, 2]

enquiries = [
    # ── PART 1 — Approving or amending the Draft Contract ──────────────────────
    {
        "code": "A1",
        "section": "Contract",
        "topic": "Title number mismatch between title documents and contract",
        "trigger": "title numbers on official copies and contract are different",
        "text": "We note that the Title Number referred to in the documents of title supplied and the Title Number on the Contract document are different. Please clarify."
    },
    {
        "code": "A2a",
        "section": "Contract",
        "topic": "Joint registered proprietors but sole seller on contract",
        "trigger": "registered in joint names but contract in one name",
        "text": "We note that the Property is registered in the joint names of (insert names of all Registered Proprietors) but the Contract is issued in the sole name of (insert details of Seller on contract). Please provide evidence of the non-participation of (insert name of non-selling proprietor) to the Contract."
    },
    {
        "code": "A2b",
        "section": "Contract",
        "topic": "Seller is not the registered proprietor and no authority provided",
        "trigger": "seller on contract is not registered proprietor and no probate or power of attorney supplied",
        "text": "We note that the Contract is in the name of (insert name of seller on Contract) but that the Registered Proprietor(s) of the property is/are (insert name(s) of Registered Proprietors). Please provide evidence of the seller's authority to deal with the property."
    },
    {
        "code": "A2c",
        "section": "Contract",
        "topic": "Registered owner name differs from contract surname change",
        "trigger": "name of registered owner differs on proprietorship register and contract due to change of surname",
        "text": "Please provide evidence of the change of name of (insert name of proprietor with changed name)."
    },
    {
        "code": "A2d",
        "section": "Contract",
        "topic": "Power of Attorney over 12 months old",
        "trigger": "seller selling by attorney and power of attorney over 12 months old and not EPA or LPA",
        "text": "We note that the Power of Attorney is more than 12 months old. Please confirm that there is no evidence that the power has been revoked and that an application has not been made to the Court of Protection."
    },
    {
        "code": "A2e",
        "section": "Contract",
        "topic": "Form A restriction with sole proprietor seller",
        "trigger": "Form A restriction on register and seller is a sole proprietor",
        "text": "We note the property is registered in the sole name of the seller but there is a Form A Restriction registered against the property. Please arrange either for the Restriction to be removed, or arrange for a second trustee to be appointed. If the latter, please advise as to the name of the second trustee so that we may draft the Transfer Deed."
    },
    {
        "code": "A2f",
        "section": "Contract",
        "topic": "Form A restriction with surviving tenant in common",
        "trigger": "Form A restriction and seller is surviving tenant in common",
        "text": "We note that (seller) is selling in their sole name as (the Personal Representative/Attorney of) the surviving owner, however there is a Form A Restriction registered against the property. Please arrange either for the Restriction to be removed, or arrange for a second trustee to be appointed. If the latter, please advise as to the name of the second trustee so that we may draft the Transfer Deed."
    },
    {
        "code": "A3",
        "section": "Contract",
        "topic": "Deposit not held as stakeholder",
        "trigger": "contract does not state deposit held as stakeholder",
        "text": "We note that the contract does not provide that the deposit is held by you as Stakeholder. This is not acceptable and we require special condition XX to be deleted from the contract"
    },
    {
        "code": "A4",
        "section": "Contract",
        "topic": "Limited title guarantee instead of full title guarantee",
        "trigger": "contract states limited title guarantee",
        "text": "We note that the contract states that the property will be sold with Limited Title Guarantee. We must insist that the property is sold with Full Title Guarantee and we have amended the contract accordingly."
    },
    {
        "code": "A5",
        "section": "Contract",
        "topic": "Contract approved subject to amendments",
        "trigger": "contract requires standard standard amendments",
        "text": "We enclose a copy of the Contract which is approved subject to the following amendments:\nPlease amend the contract rate to 4% above the base rate of (bank referred to in contract) (or Law Society's Rate)\nPlease delete Special Condition (?)\nPlease amend the amount of fees payable in respect of service of a Notice to Complete in spec (?) to a maximum of $f100+VAT$ (and add 'and the same shall apply mutatis mutandis in the case of default by the seller to the end of the condition.\nPlease delete our email address from the Contract, we do not accept service of documents by email.\nPlease confirm your agreement to the proposed amendments"
    },
    {
        "code": "A6a",
        "section": "Contract",
        "topic": "Seller selling under General or Special Power of Attorney",
        "trigger": "Power of Attorney is not EPA or LPA",
        "text": "We note that the seller is selling under a General/Special Power of Attorney. Please confirm that the donor or the Power of Attorney has not lost capacity."
    },
    {
        "code": "A6b",
        "section": "Contract",
        "topic": "Power of Attorney over 12 months old confirmation",
        "trigger": "Seller selling by Attorney and Power of Attorney over 12 months old and not EPA or LPA",
        "text": "We note that the Power of Attorney is more than 12 months old. Please confirm that there is no evidence that the power has been revoked and that an application has not been made to the Court of Protection."
    },
    {
        "code": "A7",
        "section": "Contract",
        "topic": "Unregistered Enduring Power of Attorney",
        "trigger": "seller selling under an unregistered Enduring Power of Attorney",
        "text": "We note that the seller is selling under an unregistered Enduring Power of Attorney. Please confirm that you are not aware of any circumstances that would require registration of the Power with the Court of Protection."
    },
    {
        "code": "A8",
        "section": "Contract",
        "topic": "Land Registry identity compliance for Power of Attorney",
        "trigger": "seller selling under a Power of Attorney requiring identity confirmation",
        "text": "We note that the seller is selling under a Power of Attorney. In order to comply with HM Land Registry's identity requirements in relation to Powers of Attorney, please confirm that you act for both the donor and donee of the Power of Attorney. Alternatively, please provide evidence of identity for the donor of the Power."
    },
    {
        "code": "A9",
        "section": "Contract",
        "topic": "Certified copy of document required",
        "trigger": "hard copy certified copies needed with original stamp",
        "text": "Please supply hard copy certified copy (name of document(s)) bearing the original certification stamp and signature."
    },

    # ── PART 2 — Approving or Drafting the Transfer Deed ───────────────────────
    {
        "code": "B1",
        "section": "Transfer Deed",
        "topic": "Draft Transfer enclosed for approval",
        "trigger": "sending draft transfer deed for approval",
        "text": "We enclose draft Transfer for your approval. We have sent the same to our client for execution"
    },
    {
        "code": "B2",
        "section": "Transfer Deed",
        "topic": "Approval of draft Transfer as drawn",
        "trigger": "approving seller's draft transfer without amendments",
        "text": "We approve your draft Transfer as drawn. We have sent the same to our client for execution."
    },
    {
        "code": "B3",
        "section": "Transfer Deed",
        "topic": "Approval of draft Transfer subject to amendments",
        "trigger": "approving draft transfer subject to full names or declarations",
        "text": "We approve the draft Transfer subject to the addition of our clients' full names as above, and (any other amendments e.g. address for service if not the property, joint ownership declaration) Please supply an engrossment for execution."
    },

    # ── PART 3 — TA13 Completion Information and Undertakings ──────────────────
    {
        "code": "C1",
        "section": "TA13 Completion Information",
        "topic": "Form TA13 enclosed for completion",
        "trigger": "sending Form TA13 for early completion",
        "text": "We enclose Form TA13 for your early completion."
    },
    {
        "code": "C2a",
        "section": "TA13 Completion Information",
        "topic": "Adoption of Code for Completion by Post required",
        "trigger": "seller not prepared to adopt Code for Completion by Post",
        "text": "We note from your responses to the TA13 that you are not prepared to adopt the Code for Completion by Post. We must insist that the same is adopted, please supply a further form duly amended"
    },
    {
        "code": "C2b",
        "section": "TA13 Completion Information",
        "topic": "Adoption of Code for Completion by Post in full required",
        "trigger": "seller limiting adoption of Code for Completion by Post",
        "text": "We note from your responses to the TA13 that you are not prepared to adopt the Code for Completion by Post in full. We must insist that the same is adopted in its entirety, please supply a further form duly amended agreeing to adopt the Code without any limitations."
    },
    {
        "code": "C2c",
        "section": "TA13 Completion Information",
        "topic": "Charges mismatch on TA13 and Charges Register",
        "trigger": "details of charges in TA13 paragraph 5.1 do not correspond with Charges Register",
        "text": "The details of the Charge(s) to be redeemed in paragraph 5.1 of your TA13 does not correspond with the charge(s) in the Charges Register, please supply a further form showing the correct details of the Charge(s)"
    },
    {
        "code": "C2d",
        "section": "TA13 Completion Information",
        "topic": "Unequivocal undertaking for charge redemption required",
        "trigger": "responses to paragraph 5.1 limit scope of undertaking to redeem charges",
        "text": "We note that your responses to para 5.1 limit the scope of the undertaking in respect of redemption of the Charge(s) registered against the property. We must insist on an unequivocal undertaking in this regard, please supply a further form duly amended with an unequivocal undertaking."
    },
    {
        "code": "C2e",
        "section": "TA13 Completion Information",
        "topic": "Undertaking for financial entries without DS1",
        "trigger": "financial entries against property that will not be removed by DS1",
        "text": "We note that there financial entries against the property (e.g. Notice) which will not be removed from the registers by way of a DS1 or electronic equivalent. Please provide an undertaking in respect of the (give details of relevant entry) that you will discharge the same and provide the (appropriate document for its removal e.g. CN1, RX4, K11)"
    },

    # ── PART 4 — Official Copies and Filed Plan ────────────────────────────────
    {
        "code": "D1",
        "section": "Official Copies",
        "topic": "Official copy entries not provided",
        "trigger": "no official copies supplied",
        "text": "Please provide up to date Official Copy Entries and Title Plan."
    },
    {
        "code": "D2",
        "section": "Official Copies",
        "topic": "Official copies out of date",
        "trigger": "official copies more than 6 or 12 months old",
        "text": "We note that the Official Copy Entries supplied are more than 12(6) months old. Please provide up to date Official Copy Entries."
    },
    {
        "code": "D3",
        "section": "Official Copies",
        "topic": "Additional title number referred to in official copies",
        "trigger": "official copies make reference to another title number",
        "text": "The Official Copies supplied also make reference to Title Number (insert Title Number) Please provide up to date Official Copy Entries and Title Plan relating to this title and confirm that this title is to be included in the sale to our client."
    },
    {
        "code": "D4",
        "section": "Official Copies",
        "topic": "Missing deed or document referred to in title register",
        "trigger": "title register refers to deed or document not supplied",
        "text": "We note that the Title Registers refer to a Transfer/Conveyance/Deed/Plan dated (insert date) at entry X of the Property/Charges Register. Please provide a copy of the same."
    },
    {
        "code": "D5",
        "section": "Official Copies",
        "topic": "Seller registered proprietor for less than 6 months",
        "trigger": "seller registered as owner for less than 6 months",
        "text": "We note that the Seller(s) has/have been registered as the Registered Proprietor for less than 6 months. Please advise us of the reasons for the re-sale in this time period order that we can advise our lender as required under the Lenders' Handbook."
    },
    {
        "code": "D6a",
        "section": "Official Copies",
        "topic": "Restriction in favour of Management Company",
        "trigger": "Restriction in proprietorship register in favour of a management company",
        "text": "We note that there is a Restriction registered in the proprietorship register in favour of XXXXX. Please provide us with the requirements of the Management Company in order to comply with the terms of the Restriction."
    },
    {
        "code": "D6b",
        "section": "Official Copies",
        "topic": "Restriction in favour of an individual",
        "trigger": "Restriction registered in favour of an individual",
        "text": "Please confirm that that (enter name of Restrictioner) is aware of the proposed sale of the Property and provide us with your undertaking to provide executed documentation and form RX3/RX4 in order to remove the Restriction."
    },
    {
        "code": "D6c",
        "section": "Official Copies",
        "topic": "Restriction in favour of Local Authority within 10 years",
        "trigger": "Restriction in favour of Local Authority within 10 years of Right to Buy",
        "text": "We note there is a Restriction in favour of the Local Authority at entry (B?). Please confirm that the Local Authority have been served with notice of the seller's intention to sell and have either confirmed that they do not wish to re-purchase the property or the necessary time has elapsed since notice was served and provide evidence of the same."
    },
    {
        "code": "D7",
        "section": "Official Copies",
        "topic": "Unexpired Local Authority Discount Charge",
        "trigger": "unexpired Local Authority Discount Charge registered against property",
        "text": "We note that there is an unexpired Local Authority Discount Charge registered against the Property which will repayable on completion. Please confirm that there are sufficient funds to pay all monies owing to the Local Authority and provide us with your Undertaking that you will provide evidence that all monies have been paid on completion and that you will supply evidence of discharge in a form acceptable to HM Land Registry."
    },
    {
        "code": "D8",
        "section": "Official Copies",
        "topic": "Flying freehold missing rights of support",
        "trigger": "part of property forms a flying freehold without necessary rights",
        "text": "We note that part of the Property forms a Flying Freehold, but the title documents do not appear to provide the necessary rights of support, repair, maintenance or protection. We will therefore require an indemnity policy to be supplied at the Seller's expense. We enclose draft indemnity policy and we would be grateful if you could confirm the Seller will make an allowance in respect of the cost of the same at completion, and that any assumptions made in the draft policy are correct."
    },
    {
        "code": "D9",
        "section": "Official Copies",
        "topic": "Caution registered against property",
        "trigger": "Caution registered against property in title register",
        "text": "We note that a Caution has been registered against the Property in favour of (insert details of Cautioner). Please either arrange for the same to be removed, or provide an Undertaking that on completion you will provide a fully completed and executed WCT Form in respect of the Caution, and will satisfy any requisitions raised by HM Land Registry in respect of the same."
    },
    {
        "code": "D10",
        "section": "Official Copies",
        "topic": "Unknown covenants in referred document",
        "trigger": "title registers refer to unknown covenants in a missing document",
        "text": "We note that the title registers refer to unknown covenants contained in a (insert details of document). Please provide any documentation held with the title deeds which purport to contain details of the covenants. Alternatively we will require an Indemnity Insurance policy to be obtained at the Sellers expense. We enclose draft indemnity policy and we would be grateful if you could confirm the Seller will make an allowance in respect of the cost of the same at completion, and that any assumptions made in the draft policy are correct."
    },
    {
        "code": "D11",
        "section": "Official Copies",
        "topic": "Freehold Rentcharge compliance",
        "trigger": "property is subject to a Freehold Rentcharge",
        "text": "We note that the property is subject to a Freehold Rentcharge. Please provide evidence that the same has been paid up to date and details of the Rentcharge owner and any requirements they have in respect of service Notice of Transfer, including any fee payable."
    },

    # ── PART 5 — Property Information Form ─────────────────────────────────────
    {
        "code": "E1",
        "section": "Property Information Form",
        "topic": "Awaiting Protocol Forms",
        "trigger": "protocol forms not yet received",
        "text": "We look forward to receiving completed Protocol Forms in due course and reserve the right to raise further enquiries on the same."
    },
    {
        "code": "E2",
        "section": "Property Information Form",
        "topic": "Incomplete sections of Property Information Form",
        "trigger": "seller left sections of Property Information Form incomplete",
        "text": "The seller has not completed sections (insert details of all incomplete sections) of the Property Information Form. Please ask the seller to provide full responses to the same."
    },
    {
        "code": "E3",
        "section": "Property Information Form",
        "topic": "Missing pages from Property Information Form",
        "trigger": "pages missing from copy of Property Information Form",
        "text": "We note that pages (insert details) are missing from the copy Property Information Form supplied with the Draft Contract Pack, please supply copies of the same."
    },
    {
        "code": "E4",
        "section": "Property Information Form",
        "topic": "Originals of copy documents held on completion",
        "trigger": "confirming originals of documents supplied with PIF will be handed over",
        "text": "Please confirm that you are holding the originals of the copy documents supplied with the Property Information Form and that the originals will be handed over at completion."
    },
    {
        "code": "E5",
        "section": "Property Information Form",
        "topic": "Missing documents referred to in Property Information Form",
        "trigger": "seller refers to documents in PIF not included in pack",
        "text": "The Seller refers to (list documents if not many)/a number of documents in the Property Information Form but copies of the same were not included with the contract documents. Please provide copies of the same, and confirm that you hold the originals and that these will be handed over at completion."
    },
    {
        "code": "E6",
        "section": "Property Information Form",
        "topic": "Parking permit details not provided",
        "trigger": "seller indicates parking permit required but no details given",
        "text": "The seller has indicated that a parking permit is required to park at/outside the property but not provided details of the same. Please provide further details as to how to obtain a permit and the costs of the same."
    },
    {
        "code": "E7",
        "section": "Property Information Form",
        "topic": "EPC not supplied",
        "trigger": "no EPC provided and none available online",
        "text": "The seller has not supplied an EPC and no EPC is available via the online register. Please have the seller obtain and supply a valid EPC for the property."
    },
    {
        "code": "E8",
        "section": "Property Information Form",
        "topic": "Expired EPC provided",
        "trigger": "copy EPC supplied or online EPC has expired",
        "text": "The copy EPC supplied/available via the online register has expired. Please have the seller obtain and supply a valid EPC for the property."
    },
    {
        "code": "E9",
        "section": "Property Information Form",
        "topic": "Occupier consent required",
        "trigger": "occupiers at property who need to sign consent",
        "text": "We note from the Property Information Form that (name of occupier(s)) is/are currently (an) occupier(s) at the Property. Please confirm that they are agreeable to the sale of the Property and will sign the contract to confirm vacant possession will be given on completion, and that you will not allow exchange to take place until you are in possession of the necessary signed consent."
    },
    {
        "code": "E10",
        "section": "Property Information Form",
        "topic": "Tenants vacating notice and vacant possession",
        "trigger": "property has tenants needing notice to vacate before exchange",
        "text": "Please advise if notice has been served on the tenants and when they are due to vacate the property. Please note that we will be advising our clients not to exchange contracts until such time as the property is vacant and has been reinspected."
    },
    {
        "code": "E11",
        "section": "Property Information Form",
        "topic": "Property Information Form not signed and dated",
        "trigger": "Property Information Form lacks correct signature and date",
        "text": "We note that the Property Information Form has not been correctly signed and dated. (If we have been sent original) We return this form for signature and return. (If we have been sent a copy) Please arrange for the same to be signed and dated and provide a further copy."
    },
    {
        "code": "E12",
        "section": "Property Information Form",
        "topic": "Property Information Form over 6 months old",
        "trigger": "Property Information Form completed more than 6 months ago",
        "text": "We note that the Property Information Form was completed over 6 months ago. Please confirm that the Seller has had sight of the form and can confirm that their responses remain the same, and if not, please advise of any changes or supply a revised form."
    },

    # ── PART 6 — Alterations/Extensions/Works ──────────────────────────────────
    {
        "code": "F1",
        "section": "Alterations",
        "topic": "Building works details and planning consents",
        "trigger": "seller indicated building works carried out",
        "text": "The seller has indicated that there have been (building works/details) at the property, please ask the seller to provide further details in respect of the same, including any necessary Planning Permission/Building Regulations or other consents necessary."
    },
    {
        "code": "F2a",
        "section": "Alterations",
        "topic": "Alterations consent under Restrictive Covenants unknown date",
        "trigger": "alterations require consent under restrictive covenants and date unknown",
        "text": "We note that that alterations have been carried out to the Property which appear to require consent under the Restrictive Covenants contained in the title. Please provide evidence that the relevant consent was obtained.\nPlease also confirm the date the works were carried out at the property. If the work was carried out more than 20 years ago and consent was not obtained, please confirm that there is nothing to suggest that any action is being taken or threatened in respect of the breach in order to allow us to proceed with this matter. If the breach occurred less than 20 years ago then unless you already hold consent to the alterations carried out then we will require Indemnity Insurance to be obtained at the Sellers expense. We enclose draft indemnity policy and we would be grateful if you could confirm the Seller will make an allowance in respect of the cost of the same at completion, and that any assumptions made in the draft policy are correct."
    },
    {
        "code": "F2b",
        "section": "Alterations",
        "topic": "Alterations consent under Restrictive Covenants under 20 years",
        "trigger": "alterations require consent under restrictive covenants and works under 20 years old",
        "text": "Unless you already hold consent to the alterations carried out, then we will require an Indemnity Insurance policy to be obtained at the Seller's expense. We enclose draft indemnity policy and we would be grateful if you could confirm the Seller will make an allowance in respect of the cost of the same at completion, and that any assumptions made in the draft policy are correct."
    },
    {
        "code": "F3",
        "section": "Alterations",
        "topic": "FENSA certificate for replacement windows",
        "trigger": "windows or doors replaced, no FENSA certificate provided",
        "text": "Please provide a copy of the FENSA Certificate in respect of the replacement windows/doors installed at the property in (year)"
    },
    {
        "code": "F3b",
        "section": "Alterations",
        "topic": "Gas Safe certificate for new boiler or central heating",
        "trigger": "new boiler or central heating installed, no Gas Safe certificate",
        "text": "Please provide a copy of the Gas Safe/CORGI certificate in respect of the new boiler/central heating system installed at the property in (year)"
    },
    {
        "code": "F3c",
        "section": "Alterations",
        "topic": "Electrical works certificate",
        "trigger": "electrical works carried out, no competent persons certificate",
        "text": "Please provide a copy of the relevant Building Regulations or Competent Persons Scheme certificate in respect of electrical works carried out at the property in (year)"
    },
    {
        "code": "F4",
        "section": "Alterations",
        "topic": "Cavity Wall Insulation guarantee and claims",
        "trigger": "property has benefit of Cavity Wall Insulation",
        "text": "We note that the property has the benefit of Cavity Wall Insulation. Please confirm that this has not caused any structural or damp issues to the property and there is no ongoing claim in relation to the same."
    },

    # ── PART 7 — Fittings and Contents Form ────────────────────────────────────
    {
        "code": "G1",
        "section": "Fittings and Contents Form",
        "topic": "Fittings and Contents Form not signed and dated",
        "trigger": "Fittings and Contents Form lacks correct signature and date",
        "text": "We note that the Fittings and Contents Form has not been correctly signed and dated. (If we have been sent original) We return this form for signature and return. (If we have been sent a copy) Please arrange for the same to be signed and dated and provide a further copy."
    },
    {
        "code": "G2",
        "section": "Fittings and Contents Form",
        "topic": "Fittings and Contents Form over 6 months old",
        "trigger": "Fittings and Contents Form completed over 6 months ago",
        "text": "We note that the Fittings and Contents Form was completed over 6 months ago. Please confirm that the Seller has had sight of the form and can confirm that their responses remain the same, or alternatively provide an up-to-date form."
    },
    {
        "code": "G3a",
        "section": "Fittings and Contents Form",
        "topic": "Incomplete sections of Fittings and Contents Form",
        "trigger": "seller did not complete all sections of Fittings and Contents Form",
        "text": "The seller has not completed all sections of the Fittings and Contents Form (give details if necessary), please ask the seller to complete the same"
    },
    {
        "code": "G3b",
        "section": "Fittings and Contents Form",
        "topic": "Kitchen section columns incomplete",
        "trigger": "kitchen section columns in Section 2 are incomplete",
        "text": "The seller has not completed all columns in Section 2 of the Fittings and Contents Form relating to the kitchen. We presume that where an item is marked as 'fitted' it is included in the sale but please confirm."
    },
    {
        "code": "G4",
        "section": "Fittings and Contents Form",
        "topic": "Items offered for sale in Fittings and Contents Form",
        "trigger": "seller offered items for sale in Fittings and Contents Form",
        "text": "We note that the Seller has offered a number of items for sale in the Fittings and Contents Form. We are taking our client's instructions as to whether they wish to buy any of the items and will revert to you when we have their response."
    },

    # ── PART 8 — Recently Built or Altered Properties ──────────────────────────
    {
        "code": "H1",
        "section": "Recently Built or Altered Properties",
        "topic": "NHBC documentation or building guarantee",
        "trigger": "recently built property requiring NHBC or building guarantee",
        "text": "Please provide a copy of the NHBC documentation or other building guarantee relating to the Property and confirm that the original will be handed over on completion."
    },
    {
        "code": "H2",
        "section": "Recently Built or Altered Properties",
        "topic": "Copy planning permission for development",
        "trigger": "requesting planning permission for development location",
        "text": "Please provide copy planning permission relating to the development on which the property is located."
    },
    {
        "code": "H3",
        "section": "Recently Built or Altered Properties",
        "topic": "Alterations within last 10 years or listed building",
        "trigger": "alterations carried out within last 10 years or listed building status",
        "text": "We note that the following alterations/extensions have been carried out to the Property:\n(insert details of works)\nPlease confirm the date the work was carried out. If the work was carried out within the last ten years, or the property is a Listed Building, please provide copy Planning Permission, Building Regulation Approval and/or Listed Building Consent in respect of the work. If you are unable to provide the necessary planning documentation then please note that we will require an Indemnity Insurance policy to be provided at the Seller's expense."
    },

    # ── PART 9 — Rights of Way ─────────────────────────────────────────────────
    {
        "code": "J1",
        "section": "Rights of Way",
        "topic": "Unadopted road access enquiry",
        "trigger": "access road not adopted by local authority",
        "text": "We note that XXXXX is not a public highway and is not adopted by the Local Authority. Please confirm whether the Seller has ever encountered any problems exercising the right of way to gain access to the property and whether any contributions have been requested or made in respect of the maintenance and repair of access"
    },
    {
        "code": "J2",
        "section": "Rights of Way",
        "topic": "Unadopted road access and no formal right of way",
        "trigger": "access road unadopted and no formal rights of way in title",
        "text": "We note that XXX is not a public highway and is not adopted by the Local Authority. It would also appear that no formal rights of way exist in the title documents supplied. Please provide any evidence that there is a legal right to use the same. If this is not available, please confirm that the Seller will provide a Statutory Declaration and meet the cost of an Indemnity Insurance policy."
    },
    {
        "code": "J3",
        "section": "Rights of Way",
        "topic": "Problems or maintenance contributions for right of way",
        "trigger": "document contains right of way over specific land",
        "text": "We note from the (enter details of document containing rights) that there is a right of way over the (land coloured/hatched etc in the Transfer/Conveyance dated ???) Please advise whether the Seller has ever encountered any problems exercising the right of way and whether any contributions have been requested or made in respect of the maintenance and repair of access to the same."
    },

    # ── PART 10 — Additional Enquiry Forms ─────────────────────────────────────
    {
        "code": "K1",
        "section": "Additional",
        "topic": "Conservatory additional enquiries",
        "trigger": "conservatory present at property",
        "text": "We note that there is a Conservatory at the property. We enclose our additional Conservatory enquiries which please have the seller complete and return."
    },
    {
        "code": "K2",
        "section": "Additional",
        "topic": "Septic tank additional enquiries",
        "trigger": "septic tank present at property",
        "text": "We note that there is a Septic Tank at the property. We enclose our additional Septic Tank enquiries which please complete and return."
    },
    {
        "code": "K3",
        "section": "Additional",
        "topic": "Tenanted property additional enquiries",
        "trigger": "property being sold subject to a tenancy",
        "text": "We note that the property is being sold subject to a tenancy. We enclose our Tenanted Property enquiries which please complete and return."
    },
    {
        "code": "K4",
        "section": "Additional",
        "topic": "Solar panels enquiry",
        "trigger": "solar panels present at property",
        "text": "We note that there is are Solar Panels at the property. We enclose our additional Solar Panel enquiries which please complete and return."
    },
    {
        "code": "K5",
        "section": "Additional",
        "topic": "Freehold management enquiries",
        "trigger": "management company involved in freehold property",
        "text": "We enclose our Freehold Management Enquiries which please have the Management Company complete and return."
    }
]

def ingest_all_enquiries():
    """
    Converts all enquiry texts to vectors and stores in ChromaDB format_library collection[cite: 1]
    Run this script once — or whenever you add new enquiry formats[cite: 1]
    """

    print(f"Ingesting {len(enquiries)} enquiries into format library...")

    # Step 2: Build text to embed — combine all fields for richer search[cite: 1]
    # We embed a combination of topic + trigger + text[cite: 1]
    # so the AI can find the right enquiry by any of these[cite: 1]
    texts_to_embed = []
    for e in enquiries:
        combined = f"Code: {e['code']}. Section: {e['section']}. Topic: {e['topic']}. When to use: {e['trigger']}. Enquiry text: {e['text']}"
        texts_to_embed.append(combined)

    # Step 3: Generate embeddings[cite: 1]
    print("Generating embeddings...")
    embeddings = model.encode(texts_to_embed).tolist()

    # Step 4: Store in ChromaDB[cite: 1]
    ids = [f"enquiry_{e['code']}" for e in enquiries]
    metadatas = [
        {
            "code": e["code"],
            "section": e["section"],
            "topic": e["topic"],
            "trigger": e["trigger"]
        }
        for e in enquiries
    ]
    documents = [e["text"] for e in enquiries]   # store just the text for retrieval[cite: 1]

    format_collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    print(f"Done! {len(enquiries)} enquiries stored in format_library collection.")
    print("Enquiry codes stored:", [e["code"] for e in enquiries])

if __name__ == "__main__":
    ingest_all_enquiries()