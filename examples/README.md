# POCS Examples for Beginners

This directory contains examples to help you learn POCS, from simple CLI commands to Python scripts.

## Getting Started: The Command Line

**Most users should start with the `pocs` command line tool** - it's simpler and safer than writing Python code.

### Quick Start Hardware Check

```bash
# 1. Configure your unit (REQUIRED FIRST STEP)
pocs config setup

# 2. Test your hardware
pocs mount search-home
pocs camera take-pics --num-images 1

# 3. Run automated observing
pocs mount park
```

### Full CLI Documentation

For complete CLI documentation, see the **[CLI Guide](../docs/cli-guide.md)**.

The CLI guide includes:
- All commands (config, run, mount, camera, etc.)
- Detailed examples and options
- Common workflows
- Troubleshooting tips
- Advanced usage

## Python Examples (Advanced)

Once you're comfortable with the CLI, explore Python scripting:

### `beginner_simulation.py`

A complete Python script that demonstrates:
- Setting up the POCS environment
- Starting the configuration service
- Creating a simulated observatory
- Performing basic operations

**How to run:**
```bash
python examples/beginner_simulation.py
```

**When to use Python instead of CLI:**
- You need custom observation sequences
- You're developing new POCS features
- You're integrating POCS with other software
- You need programmatic control

**What you'll learn:**
- How to configure POCS environment variables
- How the config server works
- How to create a POCS instance from code
- Basic observatory operations via Python API

## Next Steps

After trying these examples:

1. **Master the CLI** - Practice the commands above
2. **Run simulated observations** - Use `pocs run auto` with simulators
3. **Read the documentation** - Check [docs/conceptual-overview.md](../docs/conceptual-overview.md)
4. **Explore Jupyter notebooks** - Try [notebooks/TestPOCS.ipynb](../notebooks/TestPOCS.ipynb)
5. **Join the community** - Ask questions at https://forum.projectpanoptes.org

## Quick Reference

| Task | CLI Command | Python Alternative |
|------|-------------|-------------------|
| Configure | `pocs config setup` | Edit config files manually |
| Observe | `pocs run auto` | `pocs.run()` |
| Slew mount | `pocs mount slew-to-target --target M42` | `mount.set_target_coordinates(...)` |
| Take pictures | `pocs camera take-pics` | `camera.take_exposure(...)` |
| Check status | `pocs config status` | `server_is_running()` |

## Tips for Learning

- **Start with CLI** - Master commands before diving into Python
- **Use simulators** - Test without hardware via config settings
- **Read the code** - Examples are well commented
- **Experiment** - Modify examples to learn
- **Check logs** - Look in `$PANDIR/logs/` when things go wrong
- **Ask questions** - The community is friendly and helpful!

## Help and Documentation

- **CLI help**: Run any command with `--help`, e.g. `pocs mount --help`
- **Full docs**: https://pocs.readthedocs.io
- **Forum**: https://forum.projectpanoptes.org
- **Architecture guide**: [docs/architecture-for-beginners.md](../docs/architecture-for-beginners.md)
- **Glossary**: [docs/glossary.md](../docs/glossary.md)
