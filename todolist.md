Basic TODO list for Iteration 1 (Hardening)
	1.	Create a new branch feat/iteration-1-hardening
	2.	Fix missing week handling: _get_row() must raise (no {} fallback) + add unit test
	3.	Harden export writing: writing artifacts must fail the run if disk/write fails + add test
	4.	Stop swallowing logging errors: don’t except: pass silently
	5.	Add 1 end-to-end test: CSV → run folder → artifacts exist
	6.	Run pytest + ruff check . and open PR

That’s the step-by-step path.