from setuptools import setup  # type: ignore

setup(
    name="shexting",
    version="0.1.0",
    url="https://github.com/axegon/shexting",
    packages=["shexting"],
    python_requires=">=3.9",
    install_requires=open("requirements.txt").read().split("\n"),
    entry_points={
        "console_scripts": [
            "shextingshexting=shexting.cli:main",
        ],
    },
)
