public sealed class EntitasDemoSystems : Feature
{
    public EntitasDemoSystems(GameContext game) : base("Entitas Demo")
    {
        Add(new DemoMoveSystem(game));
        Add(new DemoViewSystem(game));
    }
}
