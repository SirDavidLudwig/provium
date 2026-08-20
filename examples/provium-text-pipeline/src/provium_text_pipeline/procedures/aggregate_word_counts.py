"""Aggregation procedure implementation."""

from collections import Counter
from collections.abc import Mapping

from provium import Procedure, ProcedureProcessContext

from .catalog import AGGREGATE_DEFINITION, AggregateConfig, AggregateContract


class AggregateWordCounts(
    Procedure[
        AggregateConfig,
        AggregateContract.SetupInputs,
        AggregateContract.Inputs,
        AggregateContract.Outputs,
    ]
):
    definition = AGGREGATE_DEFINITION

    def process(
        self,
        context: ProcedureProcessContext,
        configuration: AggregateConfig,
        inputs: AggregateContract.Inputs,
        outputs: AggregateContract.Outputs,
    ) -> None:
        counts = Counter[str]()

        if inputs.previous is not None:
            with inputs.previous.open() as reader:
                counts.update(reader.read())

        for binding in inputs.token_lists:
            with binding.open() as reader:
                counts.update(reader.read())

        values: Mapping[str, int]
        if configuration.top_n and configuration.top_n > 0:
            values = dict(
                sorted(
                    ((token, count) for token, count in counts.items() if count > 0),
                    key=lambda item: (-item[1], item[0]),
                )[: configuration.top_n]
            )
        else:
            values = dict(counts)

        with outputs.counts.open() as writer:
            writer.write(values)


__all__ = ["AggregateWordCounts"]
