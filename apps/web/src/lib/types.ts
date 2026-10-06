export type UserRole = "FARMER" | "ADMIN" | "ADVISOR";

export interface UserPublic {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  is_email_verified: boolean;
}

export interface FarmerPublic {
  id: string;
  full_name: string;
  phone: string | null;
  location: string | null;
  experience_level: string | null;
  user: UserPublic;
}

export type SoilType = "LOAMY" | "CLAY" | "SANDY" | "SILTY" | "PEATY" | "CHALKY" | "UNKNOWN";
export type IrrigationType = "RAINFED" | "CANAL" | "TUBEWELL" | "DRIP" | "FLOOD" | "SPRINKLER" | "OTHER" | "UNKNOWN";

export interface Farm {
  id: string;
  name: string;
  total_area_acres: number | null;
  location: string | null;
  latitude: number | null;
  longitude: number | null;
  status: "ACTIVE" | "ARCHIVED";
  field_count: number;
}

export interface Field {
  id: string;
  farm_id: string;
  name: string;
  area_acres: number | null;
  soil_type: SoilType;
  irrigation_type: IrrigationType;
  status: "ACTIVE" | "FALLOW";
  crop_count: number;
}

export type CropStage =
  | "PLANNED" | "PLANTED" | "GERMINATION" | "VEGETATIVE" | "FLOWERING"
  | "FRUITING" | "MATURITY" | "HARVESTED" | "COMPLETED";

export type HealthStatus = "HEALTHY" | "MONITORING" | "AT_RISK" | "DISEASED";

export interface Crop {
  id: string;
  field_id: string;
  crop_type: string;
  variety: string | null;
  stage: CropStage;
  source: "MANUAL" | "AI_SUGGESTION";
  health_status: HealthStatus;
  planting_date: string | null;
  expected_harvest_date: string | null;
  actual_harvest_date: string | null;
  actual_yield: number | null;
  yield_unit: string | null;
  notes: string | null;
}

export type ActivityType = "PLANTING" | "IRRIGATION" | "FERTILIZATION" | "SPRAYING" | "OBSERVATION" | "HARVEST" | "CUSTOM";

export interface CropActivity {
  id: string;
  crop_id: string;
  activity_type: ActivityType;
  status: "LOGGED" | "SCHEDULED" | "OVERDUE";
  activity_date: string;
  quantity: number | null;
  quantity_unit: string | null;
  notes: string | null;
}

export interface DashboardSummary {
  farm_count: number;
  field_count: number;
  active_crop_count: number;
  active_risk_count: number;
  active_recommendation_count: number;
}

export interface CropCandidate {
  crop_type: string;
  suitability_score: number;
  confidence: "LOW" | "MEDIUM" | "HIGH";
  explanation: string;
  limiting_factors: string[];
  risk_note: string | null;
}

export interface CropIntelligenceResponse {
  id: string;
  field_id: string;
  candidates: CropCandidate[];
  important_assumptions: string[];
  model_name: string;
  model_version: string;
  is_mock: boolean;
}

export interface WeatherResponse {
  field_id: string;
  source: string;
  fetched_at: string;
  is_stale: boolean;
  temperature_celsius: number | null;
  humidity_percent: number | null;
  rainfall_mm_last_24h: number | null;
  forecast_summary: string | null;
  extreme_weather_alert: string | null;
}

export interface RiskFinding {
  id: string;
  farm_id: string | null;
  field_id: string | null;
  crop_id: string | null;
  risk_type: "WEATHER" | "ACTIVITY_GAP" | "DISEASE" | "DATA_QUALITY" | "IRRIGATION" | "HARVEST_TIMING";
  risk_level: "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
  confidence: "LOW" | "MEDIUM" | "HIGH";
  reason: string;
  recommended_action: string | null;
  status: "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED";
}

export interface Recommendation {
  id: string;
  farm_id: string | null;
  field_id: string | null;
  crop_id: string | null;
  category: string;
  priority: "LOW" | "MEDIUM" | "HIGH";
  status: "ACTIVE" | "DISMISSED" | "COMPLETED" | "EXPIRED";
  text: string;
  trigger_reason: string;
}

export interface ReferencedEntity {
  entity_type: "farm" | "field" | "crop" | "risk" | "recommendation" | "activity";
  entity_id: string;
  label: string;
}

export interface CopilotMessage {
  id: string;
  role: "USER" | "ASSISTANT" | "SYSTEM";
  content: string;
  provider_name: string | null;
  is_mock: boolean | null;
  referenced_entities: ReferencedEntity[];
  context_freshness_warnings: string[];
  created_at: string;
}

export interface CopilotConversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface CopilotConversationDetail extends CopilotConversation {
  messages: CopilotMessage[];
}

export interface PlantVisionResponse {
  id: string;
  crop_id: string;
  result_type:
    | "HIGH_CONFIDENCE" | "LOW_CONFIDENCE" | "HEALTHY" | "REJECTED_LOW_QUALITY"
    | "REJECTED_NON_PLANT" | "UNSUPPORTED_CROP" | "SERVICE_FAILURE";
  predicted_disease: string | null;
  confidence: number | null;
  symptoms_matched: string | null;
  guidance_text: string | null;
  rejection_reason: string | null;
  model_name: string;
  model_version: string;
  is_mock: boolean;
  disclaimer: string;
}

export interface TriggeredRecommendation {
  id: string;
  category: string;
  priority: "LOW" | "MEDIUM" | "HIGH";
  text: string;
}

export interface PlantVisionDetectResponse extends PlantVisionResponse {
  health_status_updated: boolean;
  updated_health_status: HealthStatus | null;
  new_risk_count: number;
  triggered_recommendations: TriggeredRecommendation[];
}

export interface QuickScanResponse {
  status: "success" | "rejected" | "error";
  message: string;
  selected_crop: string | null;
  predicted_class: string | null;
  confidence_percent: number;
  is_disease: boolean;
  crop_mismatch: boolean;
  mismatch_message: string | null;
  disclaimer: string;
}

export interface ApiErrorBody {
  error: {
    type: string;
    message: string;
    details?: unknown;
  };
}
