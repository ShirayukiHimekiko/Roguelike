using Entitas;
using static GameMatcher;

public sealed class DemoMoveSystem : IExecuteSystem
{
    readonly IGroup<GameEntity> _movable;

    public DemoMoveSystem(GameContext context)
    {
        _movable = context.GetGroup(AllOf(DemoPosition, DemoVelocity, DemoMovable));
    }

    public void Execute()
    {
        var entities = _movable.GetEntities();
        for (var i = 0; i < entities.Length; i++)
        {
            var entity = entities[i];
            entity.ReplaceDemoPosition(
                entity.demoPosition.X + entity.demoVelocity.DX,
                entity.demoPosition.Y + entity.demoVelocity.DY);
        }
    }
}
