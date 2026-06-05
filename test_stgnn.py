from backend.ml.stgnn import infer_stgnn

print("Running ST-GNN Inference Wrapper Test...")
print("-" * 40)

# Test Dengue
res1 = infer_stgnn(district_id="dist_101", target_disease="dengue")
print(f"Dengue (dist_101): {res1}")

# Test Malaria
res2 = infer_stgnn(district_id="dist_205", target_disease="malaria")
print(f"Malaria (dist_205): {res2}")

# Test Cholera
res3 = infer_stgnn(district_id="dist_302", target_disease="cholera")
print(f"Cholera (dist_302): {res3}")

# Test Unsupported
res4 = infer_stgnn(district_id="dist_101", target_disease="hypertension")
print(f"Hypertension (unsupported): {res4}")
