export const DEMO_DATA = {
  session_id: "demo-session-999",
  demographics: {
    num_rows: 1000,
    num_columns: 8,
    columns_analyzed: ["gender", "age"],
    results: {
      gender: {
        value_counts: { Male: 613, Female: 387 },
        percentages: { Male: 61.3, Female: 38.7 },
        representation_score: 0.63,
        underrepresented_groups: [],
        has_underrepresentation: false
      },
      age: {
        value_counts: { "Under 30": 210, "30-45": 450, "Over 45": 340 },
        percentages: { "Under 30": 21, "30-45": 45, "Over 45": 34 },
        representation_score: 0.46,
        underrepresented_groups: [],
        has_underrepresentation: false
      }
    }
  },
  performance: {
    overall_metrics: { accuracy: 0.72, precision: 0.74, recall: 0.72, f1: 0.73 },
    results: {
      gender: {
        groups: {
          Male: { count: 613, accuracy: 0.78, precision: 0.81, recall: 0.78, f1: 0.79 },
          Female: { count: 387, accuracy: 0.62, precision: 0.65, recall: 0.62, f1: 0.63 }
        },
        skipped_groups: [],
        performance_gaps: {
          accuracy: { gap: 0.16, flagged: true, best_group: "Male", worst_group: "Female" }
        }
      }
    }
  },
  fairness: {
    num_rows: 1000,
    protected_column: "gender",
    positive_label: 1,
    groups: ["Female", "Male"],
    group_stats: {
      Female: { count: 387, approval_rate: 0.28, tpr: 0.52 },
      Male: { count: 613, approval_rate: 0.45, tpr: 0.68 }
    },
    metrics: {
      demographic_parity_difference: { value: 0.17, flagged: true, result: "FAIL" },
      equal_opportunity_difference: { value: 0.16, flagged: true, result: "FAIL" },
      disparate_impact_ratio: { value: 0.62, flagged: true, result: "FAIL" }
    }
  },
  proxies: {
    num_high_risk: 1,
    num_features_analyzed: 5,
    features: [
      { feature: "zip_code", proxy_risk_score: 0.42, flagged: true, risk_level: "HIGH RISK" },
      { feature: "years_experience", proxy_risk_score: 0.12, flagged: false, risk_level: "LOW RISK" }
    ]
  },
  mitigation: {
    before: { accuracy: 0.72, demographic_parity_difference: 0.17, equal_opportunity_difference: 0.16, disparate_impact_ratio: 0.62 },
    after: { accuracy: 0.70, demographic_parity_difference: 0.04, equal_opportunity_difference: 0.03, disparate_impact_ratio: 0.91 },
    accuracy_cost: 0.02,
    fairness_improvement: 0.13,
    eod_improvement: 0.13,
    dir_improvement: 0.29,
    algorithm: "Reweighing (IBM AIF360)"
  }
};
