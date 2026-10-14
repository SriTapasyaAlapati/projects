Distributed Systems Mini Project - MiniNykaa (based on the Nykaa app)
Registration No.: 23MCCE28

Documents/   ArchitectureofApp_23mcce28.doc, ParadigmsandAlgorithms_23mcce28.doc,
             RequirementSpecificationSimpleApp_23mcce28.doc, Tutorial_MiniNykaa_23mcce28.doc
MiniNykaa/   Source code (Python standard library only; pytest only for the tests)
Screenshots/ Website/ and Terminal/
MiniNykaa_Presentation_23mcce28.pptx

RUN (needs only Docker):
    cd MiniNykaa
    docker compose up --build
  Wait for the "MiniNykaa is READY" banner, then open  http://localhost:8080
  Stop with Ctrl+C, then:  docker compose down

TESTS (needs Python 3.8+ ; uses a virtual environment):
    cd MiniNykaa
    python -m venv .venv                     (Linux/macOS: python3 -m venv .venv)
    .venv\Scripts\Activate.ps1               (Windows PowerShell)
    .venv\Scripts\activate.bat               (Windows cmd)
    source .venv/bin/activate                (Linux/macOS)
    pip install -r requirements-dev.txt
    pytest                                   (65 tests, ~30 s; starts its own private copy of the system)

TESTS WITH LIVE LOGS (to watch the system's logs while the tests run):
  By default, pytest starts its own private copy of the system and hides that
  copy's output, so no logs appear. To see logs, test the system that is
  already running instead:

    Terminal 1 - start the system and leave it running:
        cd MiniNykaa
        docker compose up --build
        (wait for the "MiniNykaa is READY" banner)

    Terminal 2 - run the tests against it:
        cd MiniNykaa
        (activate the virtual environment as shown above)
        Linux/macOS:          MININYKAA_EXTERNAL=1 pytest -v
        Windows PowerShell:   $env:MININYKAA_EXTERNAL="1"; pytest -v
        Windows cmd:          set MININYKAA_EXTERNAL=1 && pytest -v

  The logs from every request the tests send appear live in Terminal 1.
  To view them afterwards:   docker compose logs
  To follow one container:   docker compose logs -f <service-name>

  Notes for this mode:
    - Tests that kill and restart nodes ("destructive" ones) are skipped,
      because they cannot stop processes inside Docker.
    - The cache-TTL test is skipped if the system's cache TTL is above 3 seconds.
    - The tests add and check real data, so they change stock on the running system.