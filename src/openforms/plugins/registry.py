from typing import TYPE_CHECKING, Callable, Generic, Iterator, TypeVar

from django.db import OperationalError

from openforms.config.models import GlobalConfiguration
from openforms.plugins.constants import UNIQUE_ID_MAX_LENGTH

if TYPE_CHECKING:
    from .plugin import AbstractBasePlugin  # noqa: F401


PluginT_co = TypeVar("PluginT_co", bound="AbstractBasePlugin", covariant=True)

# Ideally, this should be bound to "type[PluginT_co]", but is not possible as of today.
PluginTypeT = TypeVar("PluginTypeT", bound="type[AbstractBasePlugin]")


class BaseRegistry(Generic[PluginT_co]):
    """
    Base registry class for plugin modules.
    """

    module: str = ""
    """
    The name of the 'module' this registry belongs to.

    The module is the logical group of extra functionality in Open Forms on top of the
    core functionality.
    """
    _registry: dict[str, PluginT_co]

    def __init__(self):
        self._registry = {}

    def __call__(
        self, unique_identifier: str, *args, **kwargs
    ) -> Callable[[PluginTypeT], PluginTypeT]:
        def decorator(plugin_cls: PluginTypeT) -> PluginTypeT:
            if len(unique_identifier) > UNIQUE_ID_MAX_LENGTH:
                raise ValueError(
                    f"The unique identifier '{unique_identifier}' is longer than {UNIQUE_ID_MAX_LENGTH} characters."
                )
            if unique_identifier in self._registry:
                raise ValueError(
                    f"The unique identifier '{unique_identifier}' is already present "
                    "in the registry."
                )
            plugin = plugin_cls(identifier=unique_identifier)
            self.check_plugin(plugin)
            plugin.registry = self
            self._registry[unique_identifier] = plugin
            return plugin_cls

        return decorator

    def check_plugin(self, plugin: PluginT_co):
        # validation hook
        pass

    def __iter__(self):
        return iter(self._registry.values())

    def __getitem__(self, key: str) -> PluginT_co:
        return self._registry[key]

    def __contains__(self, key: str) -> bool:
        return key in self._registry

    def iter_enabled_plugins(self) -> Iterator[PluginT_co]:
        try:
            config = GlobalConfiguration.get_solo()
            assert isinstance(config, GlobalConfiguration)
            with_demos = config.enable_demo_plugins
            enable_all = False
        except OperationalError:
            # fix CI trying to access non-existing database to generate OAS
            with_demos = False
            enable_all = True

        for plugin in self:
            is_demo = getattr(plugin, "is_demo_plugin", False)
            if is_demo and not with_demos:
                continue
            elif enable_all or plugin.is_enabled:  # plugins are enabled by default
                yield plugin

    def items(self):
        return iter(self._registry.items())

    def get_choices(self):
        return [(p.identifier, p.get_label()) for p in self.iter_enabled_plugins()]
