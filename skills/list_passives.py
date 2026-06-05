import importlib.util, os
spec = importlib.util.spec_from_file_location('me', os.path.join(os.getcwd(), 'mechanics_engine.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ps = m.PASSIVE_SKILLS
print(f'Total: {len(ps)}')
for i, (k, v) in enumerate(ps.items(), 1):
    req = v.get('requisito', {})
    print(f'  {i:02d}. [{k}] nivel={v.get("nivel_minimo","?")} req={req}')
