from esg_pipeline.normalizer import to_number, standardize_unit

assert to_number('1.234,56', decimal_comma=True)==1234.56
assert standardize_unit('tCO₂e')=='tco2e'
