using Newtonsoft.Json;

namespace HelloWorld
{
    public class Event
    {
        [JsonConstructor]
        public Event(string name, int age)
        {
            Name = name;
            Age = age;
        }

        internal string Name { get; }
        internal int Age { get; }
    }
}