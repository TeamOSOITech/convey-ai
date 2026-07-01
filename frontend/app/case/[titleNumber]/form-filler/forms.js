// forms.js — defines the structure of all supported legal forms for the Form Filler tool.
// Add new form types here by following the TR1 pattern.
// Each form has: id, name, description, icon, and panels array.
// Each panel has: id (must match backend JSON key), title, description (shown in middle panel), placeholder.

export const SUPPORTED_FORMS = {
  TR1: {
    id: 'TR1',
    name: 'TR1',
    fullName: 'Transfer of Whole of Registered Title',
    description: 'HMLR form to transfer the whole of a registered title from seller to buyer.',
    icon: '🏠',
    color: 'teal',
    panels: [
      {
        id: 'panel_1',
        number: '1',
        title: 'Title number(s)',
        description: 'The title number(s) of the property being transferred. Found on the Official Copy of Register of Title (OCE).',
        placeholder: 'e.g. ABS12345'
      },
      {
        id: 'panel_2',
        number: '2',
        title: 'Property',
        description: 'The address or short description of the property as shown on the title register.',
        placeholder: 'e.g. 12 High Street, London, SW1A 1AA'
      },
      {
        id: 'panel_3',
        number: '3',
        title: 'Date',
        description: 'The completion/transfer date. Usually left blank until the day of completion and inserted by hand.',
        placeholder: 'e.g. 15 July 2025 (or leave blank until completion)'
      },
      {
        id: 'panel_4',
        number: '4',
        title: 'Transferor',
        description: 'Full legal name(s) of the seller(s). If a company, include the company number. Must match the name on the title register exactly.',
        placeholder: 'e.g. John William Smith\nor\nAcme Developments Ltd (Company No. 01234567)'
      },
      {
        id: 'panel_5',
        number: '5',
        title: 'Transferee',
        description: 'Full legal name(s) of the buyer(s) and their current address as stated in the contract.',
        placeholder: 'e.g. Jane Elizabeth Jones\nof: 45 Old Road, Birmingham, B1 2AB'
      },
      {
        id: 'panel_6',
        number: '6',
        title: 'Transferee\'s address for service',
        description: 'The address to which Land Registry should send notices after registration. Usually the property itself, or the buyer\'s solicitor\'s address.',
        placeholder: 'e.g. The Property\nor\nMessrs Smith & Co, 1 Legal Lane, London, EC1A 1AB'
      },
      {
        id: 'panel_7',
        number: '7',
        title: 'Title guarantee',
        description: 'The guarantee given by the seller. Usually "full title guarantee" for residential sales. "Limited title guarantee" may be used by personal representatives or trustees.',
        placeholder: 'Full title guarantee\nor\nLimited title guarantee'
      },
      {
        id: 'panel_8',
        number: '8',
        title: 'Consideration',
        description: 'The purchase price. If a gift or nominal consideration, state "nil" or the nominal amount.',
        placeholder: 'e.g. £350,000\nor\nThe transferee(s) confirm that the total price paid and to be paid is £350,000.'
      },
      {
        id: 'panel_9',
        number: '9',
        title: 'Capacity / Declaration',
        description: 'The capacity in which the transferor is selling — e.g. as beneficial owner, as personal representative, as trustee.',
        placeholder: 'e.g. as beneficial owner'
      },
      {
        id: 'panel_10',
        number: '10',
        title: 'Additional provisions',
        description: 'Any additional covenants, easements, rights, declarations, or special conditions. Copied from the contract or agreed between solicitors.',
        placeholder: 'e.g. The transferee covenants with the transferor to observe and perform the obligations...'
      },
      {
        id: 'panel_11',
        number: '11',
        title: 'Declaration of trust (co-ownership)',
        description: 'Only required if there are two or more buyers. States whether they hold as joint tenants or tenants in common (and in what shares).',
        placeholder: 'e.g. The transferees are to hold the property as joint tenants.\nor\nThe transferees are to hold the property as tenants in common in equal shares.'
      },
      {
        id: 'panel_12',
        number: '12',
        title: 'Execution',
        description: 'Details of who will execute the transfer. Each party signs in the presence of a witness. Company must execute by two directors, or a director and secretary, or under a power of attorney.',
        placeholder: 'e.g. Signed as a deed by [Name] in the presence of:\nWitness: ...'
      }
    ]
  }
}

// Helper — returns an array of form options for the selector UI
export const FORM_OPTIONS = Object.values(SUPPORTED_FORMS).map(f => ({
  id: f.id,
  name: f.name,
  fullName: f.fullName,
  icon: f.icon,
  description: f.description,
  color: f.color
}))