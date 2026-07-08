"""results 目录布局唯一事实源：runner/checker/report 均从这里取路径。"""
import os


class ExpLayout:
    def __init__(self, results_root: str, exp_id: str):
        self.root = os.path.join(os.path.normpath(results_root), exp_id)

    def prompts_dir(self, variant: str) -> str:
        return os.path.join(self.root, "prompts", variant)

    def prompt_path(self, variant: str, seed_id: str) -> str:
        return os.path.join(self.prompts_dir(variant), f"{seed_id}.txt")

    def image_dir(self, variant: str, seed_id: str) -> str:
        return os.path.join(self.root, "images", variant, seed_id)

    def image_path(self, variant: str, seed_id: str, k: int) -> str:
        return os.path.join(self.image_dir(variant, seed_id), f"img_{k}.png")

    def check_path(self, variant: str, seed_id: str, k: int) -> str:
        return os.path.join(self.root, "checks", f"{variant}__{seed_id}__img_{k}.json")

    def manifest_path(self) -> str:
        return os.path.join(self.root, "manifest.json")

    def metrics_path(self) -> str:
        return os.path.join(self.root, "metrics.json")

    def review_html_path(self) -> str:
        return os.path.join(self.root, "review.html")

    def reveal_html_path(self) -> str:
        return os.path.join(self.root, "reveal.html")

    def final_report_path(self) -> str:
        return os.path.join(self.root, "final_report.md")
