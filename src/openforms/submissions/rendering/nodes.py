import logging
from dataclasses import dataclass
from typing import Iterator

from ..models import SubmissionStep
from .base import Node
from .constants import RenderModes

logger = logging.getLogger(__name__)


class FormNode(Node):
    """
    Render node for the submission form.
    """

    @property
    def is_visible(self):
        if self.mode == RenderModes.export:
            return False
        return True

    def get_children(self) -> Iterator:
        """
        Emit no child nodes.
        """
        return iter([])

    def render(self) -> str:
        """
        Emit the (public) name of the submission form.
        """
        form = self.renderer.form
        return form.name


@dataclass
class SubmissionStepNode(Node):
    """
    Render node for a single submission step.

    This node is only considered 'visible' if the step is applicable (determined by
    form logic). If the step is not visible, no child nodes are emitted.

    Rendering this node outputs the name of the step within the form.
    """

    step: SubmissionStep

    @property
    def is_visible(self) -> bool:
        # determine if the step as a whole is relevant or not. The stap may be not
        # applicable because of form logic.
        logic_evaluated = getattr(self.step, "_form_logic_evaluated", False)
        if not logic_evaluated:
            logger.warning(
                "You should ensure that the form logic is evaluated before rendering "
                "steps! Submission ID: %s, renderer: %r, step ID: %s",
                self.step.submission.uuid,
                self.renderer,
                self.step.uuid,
            )
        return self.step.is_applicable

    def render(self) -> str:
        if self.mode == RenderModes.export:
            return ""
        form_definition = self.step.form_step.form_definition
        return form_definition.name

    def get_children(self) -> Iterator[Node]:
        if not self.is_visible:
            return

        return iter([])  # until we have the formio thing set up

        # # at this point, hand over to the formio specific implementation details
        # formio_configuration_node = FormioConfigurationNode(
        #     step=self.step, renderer=self.renderer
        # )
        # yield from formio_configuration_node
