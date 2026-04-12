# Implementation Plan: SmartHome Matchmaker (Real Estate & Rental Recommender)

## Goal Description
Build a web application aimed at newlyweds and first-time homebuyers. Users can input natural language prompts detailing their current status, budget, and lifestyle (e.g., "I am a newlywed with 500M KRW in cash. I eat out often."). The application will process this input to match them with suitable apartments using the **RICHGO** dataset (for prices and transport) and **SPH's consumption data** (for lifestyle and commercial area habits). Once an apartment is selected, the application will provide follow-up recommendations for moving services and rental appliances using the **AJD** dataset, providing an end-to-end relocation and settlement service.

This approach perfectly aligns with the Hackathon's goal of generating business value while utilizing the mandated datasets and Snowflake's core AI capabilities.

> [!IMPORTANT]
> ## User Review Required
> Please review the technology stack and data models proposed below. We will need a Snowflake account to run Snowpark logic or Cortex AI functions. We can either mock this data initially or proceed if you already have the Snowflake API keys / connection credentials.
> - **Frontend**: Next.js (React) + Tailwind CSS (Premium Modern Aesthetics)
> - **Backend / DB Interface**: Python (FastAPI/Snowpark API)
> - **NLP Integration**: Snowflake Cortex LLM (to get bonus points) or OpenAI API.

---

## Architecture & Data Flow

1. **User Input (NLP)**: The user types their budget and lifestyle.
2. **LLM Extraction (Lifestyle Parameters)**: The prompt is processed through an LLM to dynamically extract a comprehensive structured logic payload covering multiple lifestyle variables mapping to our datasets:
   - *Financial constraints*: Budget max, preferred housing size, rent/purchase preference.
   - *Household composition*: Single, newlywed, family with kids (influences needed rooms and nearby schools).
   - *Dining & Food*: "Eats out often / Loves cafes" -> prioritizes areas with high SPH restaurant/cafe consumption.
   - *Delivery Usage*: "We order a lot" -> prioritizes areas with high SPH delivery food consumption.
   - *Leisure & Shopping*: "We love movies / shopping" -> prioritizes areas near malls, theaters, or high entertainment SPH data.
   - *Nature & Quiet*: "We want a quiet area" -> prioritizes low commercial density and proximity to parks/rivers (RICHGO).
   - *Pet friendliness*: "We have a dog" -> correlates with parks and veterinary densities.
   - *Health & Wellness*: "Needing hospitals nearby" -> prioritizes clinic/hospital accessibility.
   - *Education*: "We have young kids" -> prioritizes areas with high hagwon (academy) density / SPH education consumption.
   - *Transportation*: "Hate long commutes" -> prioritizes proximity to subways (<1km) and specific lines (RICHGO).
   - *Tech/Telecom*: "I game a lot" -> influences follow-up ISP or gaming package recommendations (AJD).
3. **Snowflake Query (RICHGO & SPH)**: The structured payload translates to an SQL/Snowpark query to find apartments under 500M KRW (via RICHGO) and matches the area's lifestyle/commercial density (e.g., eating out frequency via SPH consumption data).
4. **Appartment Confirmation**: The user confirms a suggested apartment.
5. **Snowflake Query (AJD)**: A follow-up query to the AJD dataset pulls up recommended moving services, telecom packages, and rental appliances fitting the new apartment type and newlywed demographic.
6. **Result Presentation**: A highly premium and interactive UI displays all this information.

---

## Proposed Changes

### Frontend (Next.js App)
- Initialize a sophisticated, modern UI.
- **Chat/Input Component**: A visually appealing search bar for the natural language input.
- **Apartment Carousel Component**: To display the apartment recommendations.
- **Checkout / Next Steps Dashboard**: Once an apartment is selected, switch to a dashboard showing rental, internet, and moving suggestions.

### Backend (Python/FastAPI & Snowpark)
- Setup a FastAPI server connecting to Snowflake via `snowflake-snowpark-python`.
- **`POST /api/analyze-prompt`**: Endpoint taking the raw string and extracting user parameters (budget, lifestyle mapping) utilizing Snowflake Cortex.
- **`POST /api/recommend-apartments`**: Connects to the **RICHGO** DB to fetch `AI Market Price (단지)` and `Subway Distance` based on parsed constraints. It also queries **SPH's consumption data** to prioritize regions aligning with the user's lifestyle patterns (e.g., matching "eats out often" with high restaurant consumption areas).
- **`POST /api/recommend-rentals`**: Connects to the **AJD** DB to propose related telecom & rental data trends based on the selected region.

---

## Verification Plan

### Automated / Unit Tests
- Test the prompt parsing logic to ensure "5억" translates to 500,000,000 correctly.
- Test the Snowpark connection functions to confirm we can read the provided dataset schema.

### Manual Verification
- Launch the Next.js frontend and mock endpoint connections.
- Ensure the user interface meets the "Rich Aesthetics" requirement (glassmorphism, vibrant gradients, micro-animations).
- Deploy the frontend and backend locally and verify the flow from string input -> apartment view -> rental dashboard.
