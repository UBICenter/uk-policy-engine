from typing import Tuple
from openfisca_core.parameters.parameter import Parameter
from openfisca_core.parameters.parameter_scale import ParameterScale
from openfisca_uk import Microsimulation, IndividualSim
from openfisca_uk_data.datasets.frs.frs_was_imputation import FRS_WAS_Imputation
from policy_engine_uk.simulation.situations import create_situation
from policy_engine_uk.simulation.reforms import create_reform, add_LVT
from openfisca_uk.reforms.presets.current_date import use_current_parameters
from policy_engine_uk.populations.metrics import headline_metrics
from policy_engine_uk.populations.charts import (
    decile_chart,
    intra_decile_chart,
    poverty_chart,
    population_waterfall_chart,
)
from policy_engine_uk.situations.metrics import headline_figures
from policy_engine_uk.situations.charts import (
    household_waterfall_chart,
    mtr_chart,
    budget_chart,
)
from policyengine_core import PolicyEngine

from openfisca_core.parameters import ParameterNode
import datetime

CURRENT_DATE = datetime.datetime.now().strftime("%Y-%m-%d")


class PolicyEngineUK(PolicyEngine):
    static_folder: str = "static"
    version: str = "0.1.10"
    cache_bucket_name: str = None#"uk-policy-engine.appspot.com"
    Microsimulation: type = Microsimulation
    IndividualSim: type = IndividualSim
    default_reform: type = use_current_parameters()
    default_dataset: type = FRS_WAS_Imputation
    client_endpoints: Tuple[str] = ("/", "/population-impact", "/household", "/household-impact", "/faq")
    api_endpoints: Tuple[str] = ("population_reform", "household_reform", "ubi", "parameters")

    def population_reform(self, params: dict = {}) -> dict:
        reform = create_reform(params)
        reformed = Microsimulation((self.default_reform, reform), dataset=self.default_dataset)
        return dict(
            **headline_metrics(self.baseline, reformed),
            decile_chart=decile_chart(self.baseline, reformed),
            poverty_chart=poverty_chart(self.baseline, reformed),
            waterfall_chart=population_waterfall_chart(self.baseline, reformed),
            intra_decile_chart=intra_decile_chart(self.baseline, reformed),
        )

    def household_reform(self, params: dict = {}) -> dict:
        situation = create_situation(params)
        reform = create_reform(params)
        baseline_config = use_current_parameters(), add_LVT()
        reform_config = use_current_parameters(), reform
        baseline = situation(IndividualSim(baseline_config, year=2021))
        reformed = situation(IndividualSim(reform_config, year=2021))
        headlines = headline_figures(baseline, reformed)
        waterfall = household_waterfall_chart(baseline, reformed)
        baseline.vary("employment_income", step=100)
        reformed.vary("employment_income", step=100)
        budget = budget_chart(baseline, reformed)
        mtr = mtr_chart(baseline, reformed)
        return dict(
            **headlines,
            waterfall_chart=waterfall,
            budget_chart=budget,
            mtr_chart=mtr,
        )

    def ubi(self, params: dict = {}) -> dict:
        reform = create_reform(params)
        reformed = Microsimulation((self.default_reform, reform), dataset=self.default_dataset)
        revenue = (
            self.baseline.calc("net_income").sum() - reformed.calc("net_income").sum()
        )
        UBI_amount = max(0, revenue / self.baseline.calc("people").sum())
        return {"UBI": float(UBI_amount)}
    
    def parameters(self, params: dict = {}) -> dict:
        baseline_parameters: ParameterNode = self.baseline.simulation.tax_benefit_system.parameters
        parameters = []
        for parameter in baseline_parameters.get_descendants():
            if isinstance(parameter, Parameter):
                parameters += [parameter]
            elif isinstance(parameter, ParameterScale):
                for bracket in parameter.brackets:
                    for attribute in ("rate", "amount", "threshold"):
                        if hasattr(bracket, attribute):
                            print(parameter.name, attribute, getattr(bracket, attribute))
                            parameters += [getattr(bracket, attribute)]
        parameters = list(filter(lambda param: hasattr(param, "metadata") and "in_policyengine" in param.metadata, parameters))
        parameters = [dict(
            title=p.metadata["short_name"],
            description=p.metadata["description"],
            default=p(CURRENT_DATE),
            value=p(CURRENT_DATE),
            summary=p.metadata["summary"],
            type=p.metadata["type"]
        ) for p in parameters]
        return dict(parameters=parameters)
        
app = PolicyEngineUK().app